import re


RULES: tuple[tuple[str, str], ...] = (
    (r"无(?:交通)?信号|无灯.{0,8}路口|右方道路来车", "无灯无标先减速，右方来车先通过。"),
    (r"抢救伤员|变动现场|标明位置", "抢救可以移，原位先标记。"),
    (r"故障|危险报警闪光灯|警告标志", "车坏先双闪，车后放警告。"),
    (r"酒后|饮酒|醉酒", "喝酒不开车，开车不喝酒。"),
    (r"雨天|雾天|能见度", "雨雾降速拉车距，灯光正确别急停。"),
    (r"转弯|掉头", "转弯让直行，右转让左转。"),
    (r"坝道|上坡|下坡", "上坡低挡稳，下坡不空挡。"),
    (r"实习期|陪同人员|高速公路", "实习上高速，陪同驾龄要三年。"),
    (r"抵押登记|质押备案|转让登记", "抵押质押要转让，相关权利人一起办。"),
)


def mnemonic_for(stem: str, explanation: str = "") -> str:
    """只返回经人工编排的口诀；匹配不上时留空，避免为了押韵改变题意。"""
    source = f"{stem}\n{explanation}"
    for pattern, mnemonic in RULES:
        if re.search(pattern, source):
            return mnemonic
    return ""
