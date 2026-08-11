#!/usr/bin/env python3
"""
Minimal btsnoop_hci.log parser, useful if you want to capture your own
traffic and verify/extend the findings in PROTOCOL.md.

On a rooted Android device (e.g. a rooted Echo Show), Bluetooth HCI packet
logging can be enabled without any extra app by editing
/system/etc/bluetooth/bt_stack.conf:

    BtSnoopLogOutput=true
    BtSnoopFileName=/data/misc/bluetooth/logs/btsnoop_hci.log

then restarting the Bluetooth process (or rebooting). The resulting log is
in the standard "btsnoop" format (same one Wireshark reads) and can be
parsed with any HCI-aware tool, or with this minimal parser.

Usage:
    python parse_btsnoop.py btsnoop_hci.log
"""
import struct
import sys

BTSNOOP_HEADER_LEN = 16
RECORD_HEADER_LEN = 24


def parse(path):
    with open(path, "rb") as f:
        data = f.read()

    magic, version, datalink = struct.unpack(">8sII", data[:16])
    assert magic == b"btsnoop\x00", "not a btsnoop file"

    offset = BTSNOOP_HEADER_LEN
    records = []
    while offset < len(data):
        if offset + RECORD_HEADER_LEN > len(data):
            break
        orig_len, incl_len, flags, drops, ts = struct.unpack(
            ">IIIIq", data[offset : offset + RECORD_HEADER_LEN]
        )
        offset += RECORD_HEADER_LEN
        pkt = data[offset : offset + incl_len]
        offset += incl_len
        records.append({"flags": flags, "timestamp": ts, "data": pkt})
    return records


def find_l2cap_interrupt_cids(records):
    """
    Watches L2CAP Connection Response frames on the signaling channel
    (CID 0x0001) to learn which dynamically-assigned CIDs correspond to
    the negotiated channels (e.g. the HID_Control/HID_Interrupt PSMs
    0x0011/0x0013 used for LED control - see PROTOCOL.md).
    """
    cids = set()
    for rec in records:
        pkt = rec["data"]
        if len(pkt) < 5 or pkt[0] != 0x02:
            continue
        acl_len = pkt[3] | (pkt[4] << 8)
        l2cap = pkt[5 : 5 + acl_len]
        if len(l2cap) < 4:
            continue
        cid = l2cap[2] | (l2cap[3] << 8)
        payload = l2cap[4:]
        # L2CAP signaling channel, Connection Response (code 0x03)
        if cid == 1 and payload and payload[0] == 0x03 and len(payload) >= 8:
            dcid = payload[4] | (payload[5] << 8)
            scid = payload[6] | (payload[7] << 8)
            cids.add(dcid)
            cids.add(scid)
    return cids


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    records = parse(sys.argv[1])
    print(f"{len(records)} HCI records")

    cids = find_l2cap_interrupt_cids(records)
    print(f"negotiated L2CAP CIDs seen: {sorted(cids)}")

    for rec in records:
        pkt = rec["data"]
        if len(pkt) < 5 or pkt[0] != 0x02:
            continue
        acl_len = pkt[3] | (pkt[4] << 8)
        l2cap = pkt[5 : 5 + acl_len]
        if len(l2cap) < 4:
            continue
        cid = l2cap[2] | (l2cap[3] << 8)
        payload = l2cap[4:]
        if cid in cids and payload:
            direction = "button->host" if rec["flags"] & 1 else "host->button"
            print(f"{direction:14} cid={cid:#06x} len={len(payload):3} {payload.hex()}")
