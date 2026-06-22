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


## v0.1.2

Filters the MG India stale driver-window false-positive seen when the vehicle is otherwise closed and locked. Adds a Refresh Status button so Home Assistant can request fresh values on demand.


## v0.1.3

Adds MG iSMART India brand assets for HACS/Home Assistant using the supplied MG logo.


## v0.1.4

Exposes PIN-gated remote control entities even when the India feature endpoint does not report capabilities: climate, door lock, windows, sunroof, find my car, tailgate, and heated seats. Controls still require the vehicle control PIN to be configured.


## v0.1.5

Adds a proper options/configure workflow for entering, updating, or clearing the vehicle control PIN after initial setup. The integration reloads after options changes so remote-control entities become available without deleting and recreating the integration.


## v0.1.6

Fixes the Configure/options gear error on current Home Assistant versions by using the new OptionsFlow config_entry API. Also adds the missing climate temperature unit required by Home Assistant when adding the vehicle AC control entity.


## v0.1.7

Bug-hunt/QOL pass: fixes control calls so they log in before PIN verification and poll using the returned event id, redacts phone/VIN/PIN/password from diagnostics, handles invalid PINs in the options flow without a UI crash, increases status polling tolerance, and adds regression tests for these paths.
