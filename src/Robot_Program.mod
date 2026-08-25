MODULE MainModule
!**************************************************************
! 项目: PLC-Robot-Integration-Demo  ABB机器人码垛程序
! 控制器: IRC5  机器人: IRB1200-7/0.9
! 内容: 坐标系标定流程 / 轨迹规划(垛型计算) / 速度参数 / 安全逻辑
! 版本: V2.1  日期: 2026-08-24
! 变更: V2.0 标定流程/垛型计算/安全逻辑整理
!       V2.1 改单件码垛握手: 每件DO2脉冲回报, 对应PLC逐件顺控;
!            启动命令上升沿触发, 信号粘连只执行一件;
!            新增diReset(DI2)垛位计数复位, 对接PLC满垛Q1.0;
!            修复TimeFlag共用污染(真空超时一次即永久跳过码垛);
!            删除非法IPers调用(PERS本身自动掉电保存)
! 信号: diPLCStart=PLC启动命令(DI1, 600ms脉冲)
!       diReset=PLC垛满复位命令(DI2, 换托盘时输出)
!       diSafeStop=安全回路(DI3)
!       doRobotReady=在线  doRobotDone=码垛完成(DO2, 每件脉冲)
!       doGripper=夹爪电磁阀(DO4)  diVacuumOK=真空反馈
!**************************************************************
    !---------------- 数据声明 ----------------
    ! 工具坐标系: TCP为吸盘面中心, Z+向下(工具朝向)
    PERS tooldata tGrip:=[TRUE,[[0,0,120],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    ! 工件坐标系: 以托盘前左下角为原点, Z+向上
    PERS wobjdata wPallet:=[FALSE,TRUE,"",[[600,300,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
    ! 关键点位(标定后由示教获取, 此处为示例值)
    CONST robtarget pHome:=[[300,0,400],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget pPick:=[[0,0,0],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget pPlace0:=[[0,0,0],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    ! TCP标定用参考点(4种姿态分别触碰同一点)
    CONST robtarget pCalib1:=[[400,0,300],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget pCalib2:=[[400,0,300],[0.3,0,0.95,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget pCalib3:=[[400,0,300],[0,0.3,0.95,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST robtarget pCalib4:=[[400,0,300],[-0.7,0,0.7,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    ! 垛型参数: 3行x4列x4层, 箱体外形mm
    PERS num nRows:=3;
    PERS num nCols:=4;
    PERS num nLayers:=4;
    PERS num nBoxL:=300;
    PERS num nBoxW:=200;
    PERS num nBoxH:=150;
    PERS num nApproachH:=150;   ! 接近面高度(放置/抓取上方)
    PERS num nCount:=0;         ! 已码件数(PERS自动掉电保存)
    ! 速度/转弯区参数: 空程高速, 作业低速, 到位fine
    CONST speeddata vHigh:=[1000,1000,6000,6000];
    CONST speeddata vMid:=[400,400,4000,4000];
    CONST speeddata vLow:=[100,100,2000,2000];
    CONST num zAir:=50;
    CONST num zSlow:=10;
    ! 中断与握手状态变量
    VAR intnum intEStop;
    VAR bool bEStopActive:=FALSE;
    VAR bool bCmdTO:=FALSE;     ! 启动命令等待超时(TimeFlag不会自动清零,用前置零)
    VAR bool bVacTO:=FALSE;     ! 真空反馈超时(独立标志,不与bCmdTO共用)
    VAR bool bCmdOld:=FALSE;    ! 启动命令上升沿记忆
    VAR bool bRstOld:=FALSE;    ! 复位命令上升沿记忆

    !---------------- 主程序 ----------------
    PROC main()
        rInit;
        WHILE TRUE DO
            ! PLC复位命令(DI2): 上升沿清垛位计数, 准备新托盘
            ! (满垛后PLC进入换盘步并保持Q1.0, 本循环每轮都会检查)
            IF diReset=1 AND NOT bRstOld THEN
                nCount:=0;
                TPWrite "收到复位命令, 垛位计数清零";
            ENDIF
            bRstOld:=diReset;
            ! 等PLC启动命令, 30秒超时则回等待(避免死等)
            bCmdTO:=FALSE;
            WaitDI diPLCStart,1\MaxTime:=30\TimeFlag:=bCmdTO;
            IF bCmdTO CYCLE;
            ! 上升沿才执行: 命令粘连(Q0.7持续为1)也只码一件
            IF diPLCStart=1 AND NOT bCmdOld THEN
                rPalletize;
            ENDIF
            bCmdOld:=diPLCStart;
        ENDWHILE
    ENDPROC

    !---------------- 初始化与安全挂接 ----------------
    PROC rInit()
        AccSet 100,100;                 ! 恢复默认加速度
        Reset doGripper;                ! 夹爪释放
        SetDO doRobotReady,1;           ! 通知PLC: 机器人在线
        MoveJ pHome,vHigh,zAir,tGrip\WObj:=wPallet;
        ! 急停/安全中断: diSafeStop由安全继电器辅助触点驱动
        ! 先IDelete再CONNECT, 防止程序重启动时重复挂接报错
        IDelete intEStop;
        CONNECT intEStop WITH tSafeStop;
        ISignalDI diSafeStop,1,intEStop;
    ENDPROC

    !---------------- TCP标定流程(4点法) ----------------
    PROC rCalibTCP()
        ! 原理: 以同一点(尖锥)为参考, 4种不同姿态触碰,
        ! 控制器解算TCP; 标定误差应<0.5mm, 否则重做
        TPWrite "开始TCP标定, 请手动移至参考尖点";
        MoveJ pCalib1,vLow,fine,tGrip\WObj:=wobj0;  ! 姿态1: 工具垂直向下
        Stop;                                       ! 示教器记录点1
        MoveJ pCalib2,vLow,fine,tGrip\WObj:=wobj0;  ! 姿态2: 绕X翻转约30度
        Stop;
        MoveJ pCalib3,vLow,fine,tGrip\WObj:=wobj0;  ! 姿态3: 绕Y翻转约30度
        Stop;
        MoveJ pCalib4,vLow,fine,tGrip\WObj:=wobj0;  ! 姿态4: 转到工具侧面
        Stop;
        ! 在示教器: 校准-TCP-定义中选"4点", 误差>0.5mm需重测
        ! 工件坐标系wPallet用3点法: 原点+X点+Y点(托盘两角)
        TPWrite "TCP标定完成, 请检查重定位误差";
    ENDPROC

    !---------------- 单件码垛(按垛位计数定位) ----------------
    ! PLC每送一件料发一次600ms启动命令, 本例程抓放一件并以
    ! DO2脉冲回报完成; 垛位由已码件数nCount换算(层/行/列),
    ! 隔层RelTool旋转90度压缝; 整垛完成后回Home等PLC换盘
    PROC rPalletize()
        VAR num nRowIdx;
        VAR num nColIdx;
        VAR num nLayIdx;
        VAR num nInStack;
        VAR robtarget pTarget;
        ! 由nCount换算垛位: 层内序号->行列, 整除取层数
        nInStack:=nCount MOD (nRows*nCols);
        nLayIdx:=Trunc(nCount/(nRows*nCols));
        nRowIdx:=Trunc(nInStack/nCols);
        nColIdx:=nInStack MOD nCols;
        IF nLayIdx MOD 2=1 THEN         ! 偶数层(第2/4层)旋转90度压缝
            pTarget:=RelTool(Offs(pPlace0,nRowIdx*nBoxL,nColIdx*nBoxW,nLayIdx*nBoxH),0,0,90);
        ELSE
            pTarget:=Offs(pPlace0,nRowIdx*nBoxL,nColIdx*nBoxW,nLayIdx*nBoxH);
        ENDIF
        ! 抓取: 直线进/出, 防止拖拽物料
        rApproach pPick;
        MoveL pPick,vLow,fine,tGrip\WObj:=wPallet;
        rGripper TRUE;
        MoveL Offs(pPick,0,0,nApproachH),vMid,zSlow,tGrip\WObj:=wPallet;
        ! 放置: 先到上方接近面再垂直下落
        rApproach pTarget;
        MoveL pTarget,vLow,fine,tGrip\WObj:=wPallet;
        rGripper FALSE;
        MoveL Offs(pTarget,0,0,nApproachH),vMid,zSlow,tGrip\WObj:=wPallet;
        nCount:=nCount+1;
        ! 完成握手: 每件向PLC发500ms脉冲(对应PLC顺控60步计数)
        SetDO doRobotDone,1;
        WaitTime 0.5;
        SetDO doRobotDone,0;
        ! 整垛完成: 回安全Home位, 等PLC满垛提示换托盘
        IF nCount>=nRows*nCols*nLayers THEN
            TPWrite "整垛完成, 等待PLC复位后开始新垛";
            MoveJ pHome,vHigh,zAir,tGrip\WObj:=wPallet;
        ENDIF
    ENDPROC

    !---------------- 接近子程序: 先到上方再垂直下落 ----------------
    PROC rApproach(robtarget pBelow)
        VAR robtarget pAbove;
        pAbove:=Offs(pBelow,0,0,nApproachH);
        MoveJ pAbove,vHigh,zSlow,tGrip\WObj:=wPallet;
    ENDPROC

    !---------------- 夹爪控制(带真空反馈) ----------------
    PROC rGripper(bool on)
        IF on THEN
            Set doGripper;
            bVacTO:=FALSE;              ! TimeFlag需软件清零
            WaitDI diVacuumOK,1\MaxTime:=2\TimeFlag:=bVacTO;
            IF bVacTO THEN
                TPWrite "警告: 真空未确认!";  ! 报警但不中断
            ENDIF
        ELSE
            Reset doGripper;
            WaitTime 0.3;               ! 延时防物料带起
        ENDIF
    ENDPROC

    !---------------- 安全中断: 急停处理 ----------------
    TRAP tSafeStop
        bEStopActive:=TRUE;
        StopMove;                       ! 停止当前运动
        ClearPath;                      ! 清空路径缓存
        Stop;                           ! 程序指针停在当前位置
        ! 恢复后需手动PP to Main, 确认路径无干涉再启动
    ENDTRAP

ENDMODULE
