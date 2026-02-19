"""飞书网关消息数据类 - 用于 Control Plane 与 Agent Node 之间的 WebSocket 消息传输"""

from dataclasses import dataclass, field


@dataclass
class GatewayMessage:
    """网关消息，承载飞书用户消息在 Control Plane 和 Agent Node 之间的传输"""

    message_id: str
    feishu_open_id: str
    feishu_name: str
    chat_id: str
    content: str
    msg_type: str = "text"
    media: list[str] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict:
        """序列化为字典，用于 WebSocket JSON 传输"""
        return {
            "type": "message",
            "message_id": self.message_id,
            "feishu_open_id": self.feishu_open_id,
            "feishu_name": self.feishu_name,
            "chat_id": self.chat_id,
            "content": self.content,
            "msg_type": self.msg_type,
            "media": self.media,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GatewayMessage":
        """从字典反序列化"""
        return cls(
            message_id=data.get("message_id", ""),
            feishu_open_id=data.get("feishu_open_id", ""),
            feishu_name=data.get("feishu_name", ""),
            chat_id=data.get("chat_id", ""),
            content=data.get("content", ""),
            msg_type=data.get("msg_type", "text"),
            media=data.get("media", []),
            timestamp=data.get("timestamp", ""),
        )
