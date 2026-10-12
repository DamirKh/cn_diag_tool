from io import BytesIO

from pycomm3 import Services, ClassCode, STRING
from pycomm3 import (Struct,
                     DINT,
                     STRING,
                     REAL,
                     SINT,
                     INT,
                     UDINT,
                     USINT,
                     UINT,
                     SHORT_STRING,
                     n_bytes,
    # PRODUCT_TYPES,  # defines below
                     VENDORS
                     )

# Updated datas from picomm3/cip/status_info.py
_PRODUCT_TYPES = {
    0x00: "Generic Device (deprecated)",
    0x02: "AC Drive",
    0x03: "Motor Overload",
    0x04: "Limit Switch",
    0x05: "Inductive Proximity Switch",
    0x06: "Photoelectric Sensor",
    0x07: "General Purpose Discrete I/O",
    0x09: "Resolver",
    0x0A: "General Purpose Analog I/O",
    0x0C: "Communications Adapter",
    0x0E: "Programmable Logic Controller",
    0x10: "Position Controller",
    0x13: "DC Drive",
    0x15: "Contactor",
    0x16: "Motor Starter",
    0x17: "Soft Start",
    0x18: "Human-Machine Interface",
    0x1A: "Mass Flow Controller",
    0x1B: "Pneumatic Valve",
    0x1C: "Vacuum Pressure Gauge",
    0x1D: "Process Control Value",
    0x1E: "Residual Gas Analyzer",
    0x1F: "DC Power Generator",
    0x20: "RF Power Generator",
    0x21: "Turbomolecular Vacuum Pump",
    0x22: "Encoder",
    0x23: "Safety Discrete I/O Device",
    0x24: "Fluid Flow Controller",
    0x25: "CIP Motion Drive",
    0x26: "CompoNet Repeater",
    0x27: "Mass Flow Controller, Enhanced",
    0x28: "CIP Modbus Device",
    0x29: "CIP Modbus Translator",
    0x2A: "Safety Analog I/O Device",
    0x2B: "Generic Device (keyable)",
    0x2C: "Managed Switch",
    0x2D: "CIP Motion Safety Drive Device",
    0x2E: "Safety Drive Device",
    0x2F: "CIP Motion Encoder",
    0x31: "CIP Motion I/O",
    0x32: "ControlNet Physical Layer Component",
    0xC8: "Embedded Component",
}

PRODUCT_TYPES = {
    **_PRODUCT_TYPES,
    **{v: k for k, v in _PRODUCT_TYPES.items()},
}

My_CN_Node_number = Struct(
    USINT('cn_node_number1'),
    USINT('cn_node_number2'),
    USINT('UNKNOWN1'),
    USINT('UNKNOWN2'),
)

cn_diag1_data = Struct(
    n_bytes(34, "data_diag1")
)

who = {
    "service": Services.get_attributes_all,
    "class_code": 0x1,
    "instance": 0x1,
    "connected": False,
    "unconnected_send": True,
    "route_path": True,
    "name": 'Who'
}

who_connected = {
    "service": Services.get_attributes_all,
    "class_code": 0x1,
    "instance": 0x1,
    "connected": True,
    "unconnected_send": False,
    "route_path": True,
    "name": 'Who'
}

cn_address = {
    "service": Services.get_attribute_single,
    "class_code": 0x00f0,
    "instance": 0x1,
    "attribute": 0x84,
    "connected": True,
    "unconnected_send": False,
    "data_type": My_CN_Node_number,
    "route_path": True,
    "name": 'CN_NODE_ADDR'
}
cn_diag1 = {
    "service": Services.get_attribute_single,
    "class_code": 0x00f0,
    "instance": 0x1,
    "attribute": 0x81,  # 129
    "connected": True,
    "unconnected_send": False,
    "data_type": cn_diag1_data,
    "route_path": True,
    "name": 'CN_DIAG1'
}

cn_diag_counters = {
    "service": Services.get_attribute_single,
    "class_code": 0x00f0,
    "instance": 0x1,
    "attribute": 0x82,
    "connected": False,
    "unconnected_send": True,
    # "data_type": cn_diag_counters,
    "route_path": True,
    "name": 'CN_DIAG_COUNTERS'
}

cn_diag_counters_reset = {
    "service": Services.read_tag,
    "class_code": 0x00f0,
    "instance": 0x1,
    "attribute": 0x82,
    "connected": False,
    "unconnected_send": True,
    # "data_type": cn_diag_counters,
    "route_path": True,
    "name": 'CN_DIAG_COUNTERS_RESET'
}

cn_diag_LED = {
    "service": Services.get_attribute_single,
    "class_code": 0x00f0,
    "instance": 0x1,
    "attribute": 0x83,
    "connected": False,
    "unconnected_send": True,
    # "data_type": cn_diag_counters,
    "route_path": True,
    "name": 'CN_DIAG_LED'
}


class MyModuleIdentityObject(
    Struct(
        UINT("vendor#"),
        UINT("product_type#"),
        UINT("product_code"),
        USINT("major"),
        USINT("minor"),
        n_bytes(2, "status"),
        UDINT("serial"),
        SHORT_STRING("product_name"),
    )
):
    @classmethod
    def _decode(cls, stream: BytesIO):
        values = super(MyModuleIdentityObject, cls)._decode(stream)
        values["product_type"] = PRODUCT_TYPES.get(values["product_type#"], "UNKNOWN")
        values["vendor"] = VENDORS.get(values["vendor#"], "UNKNOWN")
        values["serial"] = f"{values['serial']:08x}"
        values["rev"] = f'{values["major"]}.{values["minor"]}'

        return values


class ControlNetCounters(
        Struct(
            UINT('buffer_errors'),
            # n_bytes(8, '#error_log'),
            USINT('#err_0'),
            USINT('#err_1'),
            USINT('#err_2'),
            USINT('#err_3'),
            USINT('#err_4'),
            USINT('#err_5'),
            USINT('#err_6'),
            USINT('#err_7'),
            # n_bytes(3, '#good_frames_transmitted'),
            USINT('#0_good_frames_transmitted'),
            USINT('#1_good_frames_transmitted'),
            USINT('#2_good_frames_transmitted'),
            # n_bytes(3, '#good_frames_received'),
            USINT('#0_good_frames_received'),
            USINT('#1_good_frames_received'),
            USINT('#2_good_frames_received'),
            #
            USINT('selected_channel_frame_error'),
            USINT('channel_A_frame_error'),
            USINT('channel_B_frame_error'),
            USINT('aborted_frame_transmitted'),
            USINT('highwaters'),
            USINT('nut_overloads'),
            USINT('slot_overloads'),
            USINT('blockages'),
            USINT('non_concurrence'),
            USINT('aborted_frames_received'),
            USINT('lonely_counter'),
            USINT('duplicate_node'),
            USINT('noise_hits'),
            USINT('collisions'),
            USINT('mod_mac_id'),
            USINT('non_lowman_mods'),
            USINT('rogue_count'),
            USINT('unheard_moderator'),
            USINT('vendor_specific1'),
            n_bytes(4, 'reserved1'),
            USINT('vendor_specific2'),
            USINT('vendor_specific3'),
            n_bytes(1, 'reserved2')
        )
    ):

    @classmethod
    def _decode(cls, stream: BytesIO):
        values = super(ControlNetCounters, cls)._decode(stream)

        values['good_frames_transmitted'] = values['#2_good_frames_transmitted'] * 256 * 256 + \
                                            values['#1_good_frames_transmitted'] * 256 + \
                                            values['#0_good_frames_transmitted']
        del values['#2_good_frames_transmitted']
        del values['#1_good_frames_transmitted']
        del values['#0_good_frames_transmitted']

        values['good_frames_received'] = values['#2_good_frames_received'] * 256 * 256 + \
                                         values['#1_good_frames_received'] * 256 + \
                                         values['#0_good_frames_received']
        del values['#2_good_frames_received']
        del values['#1_good_frames_received']
        del values['#0_good_frames_received']
        return values


class ControlNetLED(
        Struct(
            USINT('smac_version'),
            n_bytes(4, 'vendor_specific'),
            n_bytes(1, 'led_state'),
        )
    ):
    @classmethod
    def _led_decode(cls, Byte: str):
        """
        :param Byte: leds state byte from req
        :return:
        Bits means:
            0,1,2 Channel A
            3,4,5 Channel B
            6 Redundancy Warning
            7 Active Channel
        Channels A/B value means:
            0 = off
            1 = solid green
            2 = flashing green+off
            3 = flashing red+off
            4 = flashing red+green
            5 = railroad red+off
            6 = railroad red+green
            7 = solid red
        """
        byte_int = Byte[0]
        LED = {
            'Redundancy_Warning': False,
            'Active_Channel': '',  # 'A' or 'B'
            'LED_A': 0,  # replace with real value
            'LED_B': 0,  # replace with real value
        }
        LED['Redundancy_Warning'] = bool(byte_int & (1 << 6))
        LED['Active_Channel'] = 'A' if bool(byte_int & (1 << 7)) else 'B'
        LED['LED_A'] = byte_int & 7  # Extract bits 0, 1, 2
        LED['LED_B'] = (byte_int >> 3) & 7  # Extract bits 3, 4, 5
        return LED

    @classmethod
    def _decode(cls, stream: BytesIO):
        values = super(ControlNetLED, cls)._decode(stream)  # values are dict type like
        leds = ControlNetLED._led_decode(values['led_state'])
        values.update(leds)
        return values
