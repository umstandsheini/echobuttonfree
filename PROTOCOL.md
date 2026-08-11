# Echo Button protocol notes

## Hardware

- Model strings seen: `EchoBtnQ53`, `EchoBtnQ4V` (identified from a
  device-info exchange during pairing, see below)
- Manufacturer string: `AMAZON`
- Firmware version seen: `1.3.1`
- Bluetooth Classic (BR/EDR) only — standard HID PSMs are used
  (0x0011 = HID_Control, 0x0013 = HID_Interrupt), plus a separate RFCOMM/SPP
  service for button state (SDP service name observed: `RFC SERVER`)
- No BLE, no persistent local storage of images/config beyond pairing state
- Community teardown (see [Matthew Petroff's writeup](https://mpetroff.net/2017/12/amazon-echo-button-teardown/))
  identifies the SoC as a Cypress/Infineon **CYW20735**
  ("single-chip Bluetooth transceiver for wireless input devices"), which
  has publicly available development tools from Infineon — relevant if you
  want to go as far as reflashing the button itself rather than just talking
  to stock firmware.

## Pairing

Standard Bluetooth Classic pairing. Hold the button until the LED changes
color/pattern to enter pairing mode, then pair from your host like any other
Bluetooth device. Once bonded, reconnecting does not require re-pairing.

Note: a button can only be actively connected to one host at a time. Pairing
it to your own hardware will not remove the old Echo pairing, but the button
will only maintain one active connection.

## Channel 1: button press/release (RFCOMM / SPP)

This is the easy part, and was already solved by the community (credit:
[Matt Crouch](https://mattcrouch.github.io/blog/2019/11/hacking-amazon-echo-buttons/) /
[`on-the-buzzer-server`](https://github.com/MattCrouch/on-the-buzzer-server/blob/master/Button.js)).
Independently confirmed against our own capture (see below).

Connect to the button over standard **RFCOMM (Serial Port Profile)**. Use
SDP to discover the channel number for the SPP service, then open a normal
serial-port-style connection. Any standard Bluetooth Classic SPP client
library works — no proprietary handshake needed for this part.

Once connected, the button periodically sends fixed-size buffers. Frames
that aren't exactly **40 bytes** can be ignored (initialization noise).
Within a 40-byte frame:

```
byte[29] == 0x02   ->  button DOWN (pressed)
byte[29] == 0x03   ->  button UP (released)
```

Minimal Node.js example (using the `bluetooth-serial-port` package):

```javascript
const { BluetoothSerialPort } = require("bluetooth-serial-port");

const BUTTON_STATE_POSITION = 29;
const btsp = new BluetoothSerialPort();

btsp.findSerialPortChannel(buttonAddress, channel => {
  btsp.connect(buttonAddress, channel, () => {
    btsp.on("data", buffer => {
      if (buffer.length !== 40) return; // not a button event
      const isPressed = buffer[BUTTON_STATE_POSITION] === 0x02;
      console.log(isPressed ? "DOWN" : "UP");
    });
  });
});
```

### Cross-check against our own capture

We independently captured Bluetooth HCI traffic (`btsnoop_hci.log`, enabled
via `BtSnoopLogOutput=true` in `bt_stack.conf` on a rooted Echo Show acting
as the host) and found periodic packets containing a byte that toggled
between `0x02` and `0x03`, at an offset consistent with the above (once you
strip the extra ATT/L2CAP framing our capture included, since we sniffed
one layer lower than the SPP abstraction the community project used). The
values and semantics line up exactly. This gives two independent
confirmations of the same 0x02/0x03 press/release encoding.

Open question for anyone continuing this: it is not yet confirmed whether
this RFCOMM/SPP channel is fully independent from the HID-PSM channels used
for LED control (see below), or whether they're two views into overlapping
state. Worth checking with a simultaneous capture of both.

## Channel 2: LED control (`GadgetController.SetLight`-style)

This part is fully custom (this is Amazon's proprietary "Alexa Gadgets"
layer) and was decoded from scratch by diffing captured packets against
known ground-truth color values from Amazon's own [Color Changer sample
skill](https://github.com/alexa/skill-sample-nodejs-buttons-colorchanger)
(`button_animations/colorsList.js` — the sample ships literal hex values
for named colors, which made it possible to identify the exact byte
positions carrying color data by triggering one known color at a time and
diffing the resulting packets byte-for-byte).

### Transport

L2CAP channels negotiated over the classic Bluetooth **HID PSMs**:
`0x0011` (HID_Control) and `0x0013` (HID_Interrupt). Connection is
initiated by the *host* (the thing controlling the LED), using standard
L2CAP `Connection Request`/`Connection Response` to get channel IDs, then
sending framed application data over those channels.

### Roll call / device info handshake

On connect, a device-info exchange happens containing (as literal ASCII
substrings in the packet):

- `AMAZON` — manufacturer
- a device-type identifier (opaque token)
- a model string, e.g. `GA000023`
- the device serial number, e.g. `G0XXXXXXXXXXQXX` (format observed:
  `G0` + digits/letters, device-specific)
- the device's own Bluetooth MAC address (embedded again in the payload)
- a model name string, e.g. `EchoBtnQ53`
- a human-readable name, `Echo Buttons`
- firmware version, e.g. `1.3.1`

This is useful for identifying which physical button you're talking to when
more than one is connected (each has a distinct serial number embedded).

There's also a distinct discovery/roll-call event visible in the traffic
carrying the literal ASCII marker `Device ID listings` — this corresponds
to the "roll call" concept from Amazon's Alexa Gadgets Toolkit
(`GameEngine.StartInputHandler` with roll-call recognizers, if you're
coming at this from the official Alexa Skill API side rather than the raw
Bluetooth side).

### LED animation frame format

Once a host->button animation packet is decoded (stripping the outer
L2CAP/framing bytes — look for a chunk of repeating fixed-size records),
each **animation step** is encoded as a flat 6-byte record, repeated back
to back for as many steps as the animation has:

```
[ duration_ms : 2 bytes, big-endian ]
[ color       : 3 bytes, raw RGB    ]
[ blend       : 1 byte  (0x00 = false / hard cut, 0x01 = true / cross-fade) ]
```

This was confirmed two ways:

1. **Color bytes**: triggered each of the 10 named colors from the sample
   skill's `colorsList.js` (`white=ffffff`, `red=ff0000`, `orange=ff3300`,
   `green=00ff00`, `dark green=004411`, `blue=0000ff`, `light blue=00a0b0`,
   `purple=4b0098`, `yellow=ffd400`, `black=000000`) one at a time via a
   custom animation that cycles through all of them with a distinct
   duration (2500ms on / 500ms off gap) — the captured 2-byte duration
   fields decode exactly to 2500 (`0x09c4`) and 500 (`0x01f4`), and the
   3-byte color fields exactly match the known hex values, in the exact
   order they were sent. No ambiguity.

2. **Blend flag**: sent the identical animation twice, once with every step
   marked `blend:true` and once `blend:false` (same colors, same durations,
   same order). Diffing the two captured packets byte-for-byte showed
   exactly one differing byte per step (20/20, no exceptions, no other
   bytes affected) — always immediately after the 3-byte color, flipping
   between `0x00` and `0x01`.

Multiple steps are just concatenated. A "breathing" animation, for example,
is 4 steps: `[1ms, black, blend] [duration, color, blend] [300ms, color,
blend] [300ms, black, blend]`, repeated N times (repeat count lives in the
outer directive, not per-step).

### Trigger semantics

Separately from the raw bytes, Amazon's higher-level API (as seen in the
sample skill) frames each `SetLight` payload with a `triggerEvent`:
`"buttonDown"`, `"buttonUp"`, or `"none"` (plays immediately/on idle). This
determines *when* the button's firmware plays the animation you sent it,
not part of the byte-level animation-step format above.

### What's *not* decoded here

- A separate, more compressed-looking encoding was found for single-color
  "solid" animations sent via a different code path
  (`setButtonDownAnimation`/`setButtonUpAnimation` with a *breathing*
  idle animation using slightly muted colors). It initially looked like a
  different compression scheme, but turned out to simply be **different,
  intentionally dimmer hex values** hand-picked by Amazon's sample skill
  authors for the idle "breathing" effect (see
  `settings.js` → `BREATH_CUSTOM_COLORS` in the sample skill), not a
  different wire format — once you know to look for the *dim* variant hex
  value instead of the plain named-color hex value, the same 6-byte record
  format above applies. Just don't assume every captured 3-byte value is
  one of the 10 "obvious" named colors — check the dimmed variants too.
- Battery level is not exposed anywhere found in this traffic — Amazon's
  Bluetooth device settings screen shows only a coarse "Normal" status
  string, not a numeric value, and no corresponding field was found on the
  wire. If it exists at all, it wasn't found in what was captured.
- Whether HID_Control (0x0011) vs HID_Interrupt (0x0013) carries which
  direction of traffic wasn't rigorously separated in this pass — both were
  observed carrying relevant data in the captures used here.

## Suggested next steps for anyone picking this up

- Build a minimal host (Raspberry Pi / ESP32 / laptop) that:
  1. Opens the RFCOMM/SPP connection for button press/release (see above,
     already solved)
  2. Separately negotiates the L2CAP channels on PSM 0x0011/0x0013 to send
     `SetLight`-style animation frames using the 6-byte-per-step format
     above
- On ESP32 specifically: button press via `esp_spp_*` (Bluedroid classic BT
  stack has mature, documented SPP client support) should be
  straightforward. The custom L2CAP/HID-PSM side for LED control will need
  lower-level L2CAP APIs and is the part most likely to need further
  experimentation.
- Verify whether the RFCOMM/SPP channel and the HID-PSM channels are truly
  independent, or whether one could be dropped in favor of the other for a
  simpler single-channel implementation.
