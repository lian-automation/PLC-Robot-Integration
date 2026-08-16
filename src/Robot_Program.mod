MODULE MainModule
!**************************************************************
! 项目: PLC-Robot-Integration-Demo  ABB机器人码垛程序
! 控制器: IRC5  机器人: IRB1200-7/0.9  版本: V2.0
! 内容: 坐标系标定流程 / 轨迹规划(垛型计算) / 速度参数 / 安全逻辑
! 信号: diPLCStart=PLC启动命令(DI1)  diSafeStop=安全回路(DI3)
!       doRobotReady=在线  doRobotDone=码垛完成(DO2)
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
    PERS num nCount:=0;         ! 已码件数
    ! 速度/转弯区参数: 空程高速, 作业低速, 到位fine
    CONST speeddata vHigh:=[1000,1000,6000,6000];
    CONST speeddata vMid:=[400,400,4000,4000];
    CONST speeddata vLow:=[100,100,2000,2000];
    CONST num zAir:=50;
    CONST num zSlow:=10;
    ! 中断变量(安全逻辑用)
    VAR intnum intEStop;
    VAR bool bEStopActive:=FALSE;
    VAR bool bTimeout:=FALSE;

    !---------------- 主程序 ----------------
    PROC main()
        rInit;
        WHILE TRUE DO
            ! 等PLC启动命令, 30秒超时则回等待(避免死等)
            WaitDI diPLCStart,1\MaxTime:=30\TimeFlag:=bTimeout;
            IF bTimeout CYCLE;
            rPalletize;
        ENDWHILE
        ERROR
            ! 握手类信号异常: 提示后原步重试
            IF ERRNO=ERR_WAITSYNCSIG THEN
                TPWrite "握手信号异常, 复位后重试";
                Retry;
            ENDIF
    ENDPROC

    !---------------- 初始化与安全挂接 ----------------
    PROC rInit()
        AccSet 100,100;                 ! 恢复默认加速度
        Reset doGripper;                ! 夹爪释放
        SetDO doRobotReady,1;           ! 通知PLC: 机器人在线
        MoveJ pHome,vHigh,zAir,tGrip\WObj:=wPallet;
        ! 急停/安全中断: diSafeStop由安全继电器辅助触点驱动
        CONNECT intEStop WITH tSafeStop;
        ISignalDI diSafeStop,1,intEStop;
        IPers nCount,"nCount";          ! 断电保持计数
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

    !---------------- 码垛主流程(轨迹规划) ----------------
    PROC rPalletize()
        VAR num r; VAR num c; VAR num l;
        VAR robtarget pTarget;
        ! 抓取: 直线进/出, 防止拖拽物料
        rApproach pPick;
        MoveL pPick,vLow,fine,tGrip\WObj:=wPallet;
        rGripper TRUE;
        MoveL Offs(pPick,0,0,nApproachH),vMid,zSlow,tGrip\WObj:=wPallet;
        ! 放置: 按行列层计算目标点, 隔层换向(压缝码垛)
        FOR l FROM 1 TO nLayers DO
            FOR r FROM 1 TO nRows DO
                FOR c FROM 1 TO nCols DO
                    IF l MOD 2=0 THEN   ! 偶数层旋转90度压缝
                        pTarget:=RelTool(Offs(pPlace0,(r-1)*nBoxL,(c-1)*nBoxW,(l-1)*nBoxH),0,0,90);
                    ELSE
                        pTarget:=Offs(pPlace0,(r-1)*nBoxL,(c-1)*nBoxW,(l-1)*nBoxH);
                    ENDIF
                    rApproach pTarget;
                    MoveL pTarget,vLow,fine,tGrip\WObj:=wPallet;
                    rGripper FALSE;
                    MoveL Offs(pTarget,0,0,nApproachH),vMid,zSlow,tGrip\WObj:=wPallet;
                    nCount:=nCount+1;
                    ! 每层之间回安全高度, 防撞已码垛型
                    IF c=nCols AND r=nRows THEN
                        MoveL Offs(pTarget,0,0,300),vMid,zAir,tGrip\WObj:=wPallet;
                    ENDIF
                ENDFOR
            ENDFOR
        ENDFOR
        SetDO doRobotDone,1;            ! 通知PLC: 整垛完成
        WaitTime 0.5;
        SetDO doRobotDone,0;
        MoveJ pHome,vHigh,zAir,tGrip\WObj:=wPallet;
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
            WaitDI diVacuumOK,1\MaxTime:=2\TimeFlag:=bTimeout;
            IF bTimeout TPWrite "警告: 真空未确认!";  ! 报警但不中断
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
