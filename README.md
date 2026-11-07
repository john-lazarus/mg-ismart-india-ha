# MG iSMART India

Lean Home Assistant custom integration for MG iSMART India vehicles.

India-only by design: it uses the MG India TAP/gateway endpoints directly instead of carrying the EU/AU/ROW abstractions from the generic MG/SAIC integration.

Don't run this and the MG SAIC integration (townsmcp/mg-saic-ha) on the same MG India account at the same time: they keep logging each other out and double the polling.

MG India allows one login session per account, so setting this up signs the MG app out on your phone. Multi-factor login (the SMS code) isn't supported yet: switch it off in the MG app's security settings first.

## Current scope
- phone/password login
- vehicle selection
- status polling
- doors/windows/boot/bonnet/lock/fuel/range/odometer/temperature/aux battery/CAN sensors
- EV battery level, charging state, plug state, charge time remaining and charging duration (electric models only; shared accounts may not get charging data)
- dynamic capability discovery
- GPS location (device tracker) and speed, only while the car reports a usable fix
- tyre pressures (only if the car reports them), side lights, dipped beam and main beam
- EV battery energy, distance and energy since last charge, charging voltage and current
- a Last Update diagnostic sensor showing when Home Assistant last refreshed successfully
- PIN-protected controls for climate, lock/unlock, windows, sunroof, tailgate, find-my-car, heated seats where supported

Polling is adaptive and set under Configure: every 30 minutes while parked (5 to 1440), every 5 minutes while charging, the AC is running or the car is moving (1 to 60).

If you add several cars from the same MG account, they share one login and take turns, so they no longer log each other out.

Remote controls (AC, lock, windows...) stay unavailable until the 4-digit control PIN is set under Configure.

AC on/off goes through MG's servers, so it only works if your MG account has the paid remote AC subscription where MG requires one.

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


## v0.1.8

Fixes MG India remote-control parameter payloads for door lock/unlock, climate, find-my-car, tailgate, windows, sunroof, and heated seats. Also adds a safe diagnostics boolean showing whether a control PIN is configured, without exposing the PIN or hash.


## v0.1.9

Adds an app-like per-vehicle remote-command busy state so other remote controls are unavailable while MG is processing a command, with Remote Command In Progress and Last Remote Command entities for visible feedback. Optional controls that are not reported for a vehicle, such as windows/sunroof/tailgate/heated seats, are no longer exposed by default. Control polling now retries once after a transient malformed TAP control response and waits longer for MG command completion.


## v0.1.10

Retries transient malformed TAP login responses seen immediately after Home Assistant restart, reducing startup unavailable states that required manual integration reload. Door lock/unlock now treats a vendor command timeout as success only if a fresh status read proves the requested lock state was actually reached.


## v0.1.11

Fixes ZS/Astor lock commands failing at PIN verification with TAP result 2 by refreshing the TAP session and retrying PIN verification once before sending the remote-control command.


## v0.2.0

Uses the mg-ismart-india-client 0.2.1 package instead of the bundled protocol code. Adds EV battery and charging sensors (Battery, Charging, Plugged In, Charge Time Remaining, Charging Duration) for electric models. The control PIN is 4 digits, and a remote command whose result the car can't confirm now reports an error instead of being resent.


## v0.2.1

Uses the mg-ismart-india-client 0.3.0 package. Adds a Charging Power sensor for electric models. Shows a clear message when multi-factor login is on for the MG account.


## v0.3.3

Uses mg-ismart-india-client 0.3.2, which logs in again when another login takes over the MG account (for example when a second car is added), instead of failing until Home Assistant restarts.

## v0.3.2

The AC uses Home Assistant's native temperature unit on newer versions. CAN Bus Active and Last Vehicle Activity are now diagnostic and off by default for new installs, because the car wakes up to answer each status poll, so they always read as active.

## v0.3.1

Parked cars now really use the parked interval: a status poll wakes the car, so CAN bus activity no longer counts as active.

## v0.3.0

Adds a GPS device tracker and Speed sensor, tyre pressure sensors, side/dipped/main beam sensors, EV Battery Energy, Distance Since Last Charge, Energy Since Last Charge, Charging Voltage and Charging Current sensors, and a Last Update diagnostic sensor. Adds Configure options for the parked and active polling intervals. Cars on the same MG account now share a single login. Note: the default parked poll interval changes from 3 minutes to 30 minutes (5 minutes while charging, AC running or the car is moving); lower it under Configure if you want the old behaviour.
