# MG iSMART India

Lean Home Assistant custom integration for MG iSMART India vehicles.

India-only by design: it uses the MG India TAP/gateway endpoints directly instead of carrying the EU/AU/ROW abstractions from the generic MG/SAIC integration.

## Current scope
- phone/password login
- vehicle selection
- read-only status polling
- doors/windows/boot/bonnet/lock/fuel/range/odometer/temperature/aux battery/CAN sensors
- dynamic capability discovery
- PIN-protected controls for climate, lock/unlock, windows, sunroof, tailgate, find-my-car, heated seats where supported

This project is not affiliated with MG, SAIC, or JSW MG Motor India.


## v0.1.1

Fixes India TAP login/gateway authentication, vehicle list parsing, status polling, and clarifies that setup expects a 10 digit Indian mobile number without +91.
