# echobuttonfree 

Reverse-engineering notes for using **Amazon Echo Buttons** (the small
puck-shaped Bluetooth buttons originally sold as an Alexa Gadgets Toolkit
accessory) **without an Echo device** — e.g. from a Raspberry Pi, ESP32,
Linux/Windows/Mac host, or Home Assistant.

Amazon officially discontinued/deprioritized Echo Buttons and the "Echo
Button Skills" program years ago, but the physical hardware is still capable
and shows up cheaply second-hand. This repo documents what was found by
combining:

- independent Bluetooth packet capture and analysis of a real Echo Show 5 /
  Echo Button pair (own hardware, rooted device, `btsnoop_hci.log` capture)
- Amazon's own official (if now legacy) [Alexa Gadgets Toolkit sample
  skills](https://github.com/alexa/skill-sample-nodejs-buttons-colorchanger),
  which conveniently ship with the exact RGB hex values used for named
  colors — giving a ground-truth reference to decode the raw Bluetooth bytes
  against
- prior community work, most notably Matt Crouch's
  ["Hacking Amazon Echo Buttons"](https://mattcrouch.github.io/blog/2019/11/hacking-amazon-echo-buttons/)
  write-up and [`on-the-buzzer-server`](https://github.com/MattCrouch/on-the-buzzer-server)
  source, which independently found and documented the button-press
  reporting format

See [`PROTOCOL.md`](PROTOCOL.md) for the technical write-up.

## Status / disclaimer

This is hobbyist reverse-engineering of an undocumented, proprietary
protocol, not an official spec. Amazon may change firmware behavior at any
time. Everything here was derived from observing traffic on hardware the
author owns; no Amazon intellectual property (firmware, binaries, private
keys) is included — only descriptions of the *on-the-wire byte layout*.

Use at your own risk. Pairing/connecting to the button with your own host
will disconnect it from any Echo device it was previously paired with.

## Quick facts

- Hardware: puck-shaped button, RGB LED ring, 2×AAA battery, Bluetooth
  Classic (BR/EDR) radio — no BLE, no speaker, no vibration motor
- Two device model variants seen in the wild: `EchoBtnQ53` and `EchoBtnQ4V`
  (functionally identical as far as this protocol is concerned)
- Two independent communication channels:
  1. **Button press/release** — reported over a standard Bluetooth Classic
     **RFCOMM / Serial Port Profile (SPP)** connection. No custom protocol
     needed to *read* button state.
  2. **LED control** — a proprietary framing (Amazon's "Alexa Gadgets"
     `GadgetController.SetLight` concept) sent over Bluetooth Classic L2CAP
     channels negotiated on the standard HID PSMs (0x0011 / 0x0013). Fully
     decoded, see below.
- No accessible battery percentage — only a coarse "Normal" state, likely
  UI-only, not exposed on the wire in what's captured here.

## Contents

- [`PROTOCOL.md`](PROTOCOL.md) — full technical write-up: pairing, roll
  call/discovery, button press format, LED animation byte format
- [`examples/`](examples) — small illustrative code snippets (not a
  polished library)
