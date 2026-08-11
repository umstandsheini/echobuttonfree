/**
 * Minimal Echo Button press/release reader over Bluetooth Classic RFCOMM/SPP.
 *
 * Technique credit: independently discovered and documented by Matt Crouch
 * (https://mattcrouch.github.io/blog/2019/11/hacking-amazon-echo-buttons/,
 * https://github.com/MattCrouch/on-the-buzzer-server) - this is an original
 * minimal re-implementation of the same approach for illustration, not a
 * copy of that code.
 *
 * Requires the button to already be paired with this host (standard OS
 * Bluetooth pairing - hold the button until its LED changes to enter
 * pairing mode).
 *
 * npm install bluetooth-serial-port
 */
const { BluetoothSerialPort } = require("bluetooth-serial-port");

const BUTTON_STATE_BYTE_OFFSET = 29;
const EXPECTED_FRAME_LENGTH = 40;
const DOWN = 0x02;

function watchButton(bluetoothAddress, onChange) {
  const conn = new BluetoothSerialPort();

  conn.findSerialPortChannel(
    bluetoothAddress,
    (channel) => {
      conn.connect(
        bluetoothAddress,
        channel,
        () => {
          console.log(`connected to ${bluetoothAddress}`);
          conn.on("data", (buffer) => {
            if (buffer.length !== EXPECTED_FRAME_LENGTH) {
              return; // not a button state frame (e.g. init noise)
            }
            const pressed = buffer[BUTTON_STATE_BYTE_OFFSET] === DOWN;
            onChange(pressed);
          });
        },
        () => console.error("connect failed")
      );
    },
    () => console.error("no serial port channel found - is it paired?")
  );

  return conn;
}

if (require.main === module) {
  const address = process.argv[2];
  if (!address) {
    console.error("usage: node read_button_spp.js AA:BB:CC:DD:EE:FF");
    process.exit(1);
  }
  watchButton(address, (pressed) => {
    console.log(pressed ? "DOWN" : "UP");
  });
}

module.exports = { watchButton };
