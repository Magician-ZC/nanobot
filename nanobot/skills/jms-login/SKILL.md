---
name: jms
description: "JMS系统自动化（远程MCP服务）：登录获取token、实时数据采集、虚假签收报表、问题件登记、寄件运单下载。当用户提到JMS、极兔、登录JMS、虚假签收、发单量、问题件、寄件运单时使用此skill。"
metadata: {"nanobot":{"emoji":"🔐","always":true}}
---

# JMS Skill（远程 MCP 服务）

> 当用户提到"JMS"、"极兔"、"虚假签收"、"发单量"、"问题件"、"寄件运单"等关键词时，**必须调用 mcp_jms_ 开头的工具**。

## 部署架构

- JMS MCP Server 独立部署在内网服务器上（streamable-http 模式，默认端口 9000）
- nanobot 通过 HTTP URL 连接，在 `~/.nanobot/config.json` 中配置：

```json
{
  "mcpServers": {
    "jms": {
      "url": "http://内网服务器IP:9000/mcp"
    }
  }
}
```

## 可用工具

### mcp_jms_jms_login
登录 JMS 系统，自动处理滑动验证码，获取 authtoken。

### mcp_jms_check_token
检查当前已保存的 authtoken 是否有效。

### mcp_jms_get_realtime_data
获取实时数据：发单量、预测量、加盟商排名。

### mcp_jms_download_false_sign_report
下载虚假签收报表 Excel。date 格式 YYYY-MM-DD，默认昨天。

### mcp_jms_register_problem_piece
问题件登记（仅网点账号），自动上传问题件图片。waybill_no 必填。

### mcp_jms_get_problem_piece_list
获取问题件列表（仅网点账号），返回未登记的运单号。

### mcp_jms_submit_waybill_download
提交寄件运单下载任务（异步）。后台自动轮询，完成后飞书通知。
**agent 不需要轮询 get_waybill_download_status，直接告诉用户"已提交，完成后飞书通知"。**

### mcp_jms_get_waybill_download_status
手动查询下载任务状态。仅供用户主动查询，agent 无需调用。

## 典型流程

1. 先调用 `mcp_jms_check_token` 检查 token
2. 如果无效，调用 `mcp_jms_jms_login` 登录
3. 调用对应的业务工具
