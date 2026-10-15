"""
create_sample_pdf.py - Generates sample AUTOSAR HLD PDFs for testing and demonstration.
Run:
    python create_sample_pdf.py
"""
import pymupdf


def create_sample_hld_pdf(filename="Sample_AUTOSAR_Powertrain_HLD.pdf"):
    doc = pymupdf.open()

    # Page 1: Title & Document Overview
    p1 = doc.new_page()
    rect1 = pymupdf.Rect(50, 50, 550, 750)
    text_p1 = """AUTOSAR HIGH-LEVEL DESIGN (HLD) SPECIFICATION
Document ID: HLD-POWERTRAIN-2026-V4.2
AUTOSAR Release: Classic Platform 4.4.0
Target ECU: EngineControlUnit_Main (ECU_Engine), BatteryManagementSystem (BMS_ECU)

1. Executive Summary & System Overview
This High-Level Design document specifies the software architecture for the Electric Vehicle Powertrain Control System (EVPCS) conforming to the AUTOSAR Classic 4.4 architecture standard. The system is responsible for torque demand arbitration, regenerative braking coordination, and thermal safety monitoring across the dual-inverter powertrain.

2. Software Architecture Scope
The EVPCS consists of multiple AUTOSAR Application Software Components (SWCs), Sensor-Actuator Software Components, and interactions with the Basic Software (BSW) stack via the Virtual Functional Bus (VFB) and Run-Time Environment (RTE).

Document Version: 4.2.1
Status: Approved for Architecture Review
Author: Powertrain Systems Architecture Team
"""
    p1.insert_textbox(rect1, text_p1, fontsize=11, fontname="helv")

    # Page 2: Software Components & Modules
    p2 = doc.new_page()
    rect2 = pymupdf.Rect(50, 50, 550, 750)
    text_p2 = """3. Software Components (SWC) Inventory

3.1 TorqueArbitration_SWC
- Type: Application Software Component (SWC)
- Purpose: Arbitrates torque requests from AcceleratorPedal_Sensor, CruiseControl_SWC, and StabilityControl_SWC.
- Source Page Hint: Section 3.1, Page 2
- Ports:
  * R-Port: R_AccelPedalPos (Interface: If_PedalPosition)
  * R-Port: R_CruiseTorqueReq (Interface: If_TorqueRequest)
  * P-Port: P_FinalTorqueCommand (Interface: If_TorqueCommand)

3.2 BatteryThermalMonitor_SWC
- Type: Sensor-Actuator Software Component
- Purpose: Monitors battery module cell temperatures, calculates cooling pump request states, and flags thermal derating.
- Ports:
  * R-Port: R_BatteryTempSensor (Interface: If_RawTemperature)
  * P-Port: P_ThermalDeratingFactor (Interface: If_DeratingStatus)
  * P-Port: P_CoolantPumpCommand (Interface: If_PumpActuation)

3.3 InverterMotorControl_SWC
- Type: Complex Device Driver / Application SWC
- Purpose: Converts target torque setpoints into 3-phase PWM gating commands via the microcontroller hardware timer units.
- Dependencies: Requires P_FinalTorqueCommand from TorqueArbitration_SWC.
"""
    p2.insert_textbox(rect2, text_p2, fontsize=11, fontname="helv")

    # Page 3: Interfaces, Ports & Signals
    p3 = doc.new_page()
    rect3 = pymupdf.Rect(50, 50, 550, 750)
    text_p3 = """4. Software Interfaces & Communication Signals

4.1 AUTOSAR Interfaces
- Interface: If_PedalPosition
  * Type: SenderReceiver
  * Description: Carries normalized driver pedal demand (0.0 to 100.0%).
- Interface: If_TorqueCommand
  * Type: SenderReceiver
  * Description: Carries signed target torque in Newton-meters (Nm) to inverter.
- Interface: If_ThermalDeratingFactor
  * Type: SenderReceiver
  * Description: Transmits engine power limits based on pack temperature.
- Interface: If_DiagnosticsService
  * Type: ClientServer
  * Description: Diagnostic fault recording interface to Dem (Diagnostic Event Manager).

4.2 Signals & Network Data Elements
- Signal: Sig_DriverTorqueDemand
  * Data Type: float32
  * Direction: Inward (from Pedal Sensor)
  * Description: Driver pedal position sampled at 10ms periodic task.
- Signal: Sig_InverterTorqueCmd
  * Data Type: int16
  * Direction: Outward (to Inverter Controller)
  * Description: Filtered and slew-rate limited torque demand transmitted over CAN-FD bus.
- Signal: Sig_PackMaxTemp
  * Data Type: uint8
  * Direction: Inward
  * Description: Maximum pack temperature in degrees Celsius (-40 to +120 C).
"""
    p3.insert_textbox(rect3, text_p3, fontsize=11, fontname="helv")

    # Page 4: End-to-End Functional Flow & Dependencies
    p4 = doc.new_page()
    rect4 = pymupdf.Rect(50, 50, 550, 750)
    text_p4 = """5. Functional Execution Flows

5.1 Torque Delivery Sequence Flow
Flow Sequence:
Step 1: Driver presses accelerator pedal; AcceleratorPedal_Sensor reads dual hall-effect analog voltage channels.
Step 2: RTE passes validated sensor reading to TorqueArbitration_SWC via R_AccelPedalPos.
Step 3: TorqueArbitration_SWC checks BatteryThermalMonitor_SWC for thermal derating limits.
Step 4: Arbitrated torque command is dispatched via P_FinalTorqueCommand to RTE.
Step 5: RTE routes signal across Com/CanTp stack to InverterMotorControl_SWC on the powertrain CAN-FD network.

6. Architectural Dependencies and Known Limitations
- TorqueArbitration_SWC requires a 10ms cyclic trigger from OsTask_Powertrain_10ms.
- BatteryThermalMonitor_SWC requires NvM (Non-Volatile Memory) block allocation for calibration storage.
- Notice: The connection between StabilityControl_SWC and TorqueArbitration_SWC is referenced in the architecture overview but the interface port definition R_ESP_Intervention is currently missing from Section 4.
- Incomplete Specification: Emergency shutdown flow under DC link overvoltage does not explicitly detail the handshake timeout with the High Voltage Interlock Loop (HVIL).
"""
    p4.insert_textbox(rect4, text_p4, fontsize=11, fontname="helv")

    doc.save(filename)
    doc.close()
    print(f"Sample PDF created: {filename}")


def create_sample_hld_v2_pdf(filename="Sample_AUTOSAR_Powertrain_HLD_v5.pdf"):
    """Creates a second version for document comparison."""
    doc = pymupdf.open()

    p1 = doc.new_page()
    rect1 = pymupdf.Rect(50, 50, 550, 750)
    text_p1 = """AUTOSAR HIGH-LEVEL DESIGN (HLD) SPECIFICATION - REVISION 5.0
Document ID: HLD-POWERTRAIN-2026-V5.0
AUTOSAR Release: Adaptive Platform 20-11 & Classic 4.4.0 (Hybrid Gateway)
Target ECU: CentralPowertrainController (HPC_ECU), BatteryManagementSystem (BMS_ECU)

1. Executive Summary & System Overview
This revision 5.0 updates the EV Powertrain architecture to support a Centralized High-Performance Computing (HPC) controller running Adaptive AUTOSAR with SOME/IP over Automotive Ethernet, alongside Classic AUTOSAR ECUs.

2. Software Architecture Scope
Replaces discrete CAN-FD signals with service-oriented communication (SOME/IP) for powertrain telemetry and incorporates predictive energy management.
"""
    p1.insert_textbox(rect1, text_p1, fontsize=11, fontname="helv")

    p2 = doc.new_page()
    rect2 = pymupdf.Rect(50, 50, 550, 750)
    text_p2 = """3. Software Components (SWC) Inventory

3.1 TorqueArbitration_SWC
- Type: Adaptive Application (ara::com Service)
- Purpose: Service-oriented torque arbitration supporting autonomous driving ADAS inputs and driver pedals.
- Interface: TorqueService (SOME/IP skeleton/proxy)

3.2 PredictiveEnergyManager_SWC
- Type: Adaptive Application
- Purpose: Uses GPS terrain and route look-ahead to optimize battery state-of-charge.

3.3 InverterMotorControl_SWC
- Type: Classic AUTOSAR SWC
- Purpose: Direct actuator control over CAN-FD gateway.
"""
    p2.insert_textbox(rect2, text_p2, fontsize=11, fontname="helv")

    doc.save(filename)
    doc.close()
    print(f"Comparison Sample PDF created: {filename}")


if __name__ == "__main__":
    create_sample_hld_pdf()
    create_sample_hld_v2_pdf()
