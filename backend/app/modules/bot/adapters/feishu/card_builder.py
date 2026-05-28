from __future__ import annotations

from typing import Any

from app.modules.bot.adapters.base import CardMessage


class FeishuCardBuilder:
    """Translate platform-agnostic CardMessage into Feishu interactive card JSON.

    Feishu card spec: https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM feishu-cards
    We target the v2 card schema used by lark-oapi SDK.
    """

    @staticmethod
    def build(card: CardMessage) -> dict[str, Any]:
        """Build a complete Feishu card JSON dict from a CardMessage."""
        header = FeishuCardBuilder._build_header(card)
        elements = FeishuCardBuilder._build_elements(card)
        card_json: dict[str, Any] = {"elements": elements}
        if header:
            card_json["header"] = header
        return card_json

    # -- stock quote card --

    @staticmethod
    def stock_quote_card(
        code: str,
        name: str,
        price: float,
        change: float,
        change_pct: float,
        volume: int,
        amount: float,
        analysis_summary: str | None = None,
    ) -> CardMessage:
        """Build a platform-agnostic stock quote CardMessage."""
        arrow = "+" if change >= 0 else ""
        color = "green" if change >= 0 else "red"

        card = CardMessage(
            title=f"{name} ({code})",
            subtitle="",
            header_color=color,
        )
        card.add_field("最新价", f"{price:.2f}")
        card.add_field("涨跌额", f"{arrow}{change:.2f}")
        card.add_field("涨跌幅", f"{arrow}{change_pct:.2f}%")
        card.add_field("成交量", f"{volume:,}")
        card.add_field("成交额", f"{amount / 1e8:.2f}亿")
        if analysis_summary:
            card.add_separator()
            card.add_text(f"分析摘要: {analysis_summary}")
        card.add_separator()
        card.add_button("详细分析", f"analyze:{code}", style="primary")
        card.add_button("K线数据", f"kline:{code}", style="default")
        return card

    # -- analysis loading card --

    @staticmethod
    def analysis_loading_card(code: str, name: str) -> CardMessage:
        """Build a loading-state card shown while analysis runs asynchronously."""
        card = CardMessage(
            title=f"正在分析 {name} ({code})",
            header_color="orange",
        )
        card.add_text("量化分析进行中，请稍候...")
        card.add_note("分析通常需要 10-30 秒，结果将在此卡片中更新")
        return card

    # -- analysis result card --

    @staticmethod
    def analysis_result_card(
        code: str,
        name: str,
        summary: str,
        signals: list[dict[str, str]],
        score: int | None = None,
    ) -> CardMessage:
        """Build a card that displays completed analysis results."""
        color = "green" if score and score >= 70 else ("orange" if score and score >= 40 else "red")
        title = f"分析报告: {name} ({code})"
        if score is not None:
            title += f" - 综合评分 {score}"

        card = CardMessage(title=title, header_color=color)
        card.add_text(summary)
        card.add_separator()

        for sig in signals:
            label = sig.get("name", "")
            value = sig.get("detail", "")
            card.add_field(label, value)

        card.add_separator()
        card.add_button("重新分析", f"analyze:{code}", style="primary")
        card.add_button("查看K线", f"kline:{code}", style="default")
        card.add_note("数据仅供参考，不构成投资建议")
        return card

    @staticmethod
    def dragon_tiger_card(
        title: str,
        message: str,
        items_count: int,
        top_items: list[dict[str, Any]],
    ) -> CardMessage:
        card = CardMessage(title=title, header_color="orange")
        card.add_text(message)
        card.add_separator()
        for item in top_items[:5]:
            change_pct = item["change_pct"]
            change_str = f"+{change_pct:.2f}%" if change_pct >= 0 else f"{change_pct:.2f}%"
            net_buy_str = f"{item['net_buy'] / 1e8:.2f}亿" if item["net_buy"] else "N/A"
            field_label = f"{item['name']}({item['code']})"
            field_value = f"涨幅{change_str} 净买入{net_buy_str}"
            card.add_field(field_label, field_value)
        if items_count > 5:
            card.add_note(f"共 {items_count} 条记录，仅展示前 5 条")
        return card

    @staticmethod
    def limit_up_card(
        title: str,
        message: str,
        items_count: int,
        top_items: list[dict[str, Any]],
    ) -> CardMessage:
        card = CardMessage(title=title, header_color="red")
        card.add_text(message)
        card.add_separator()
        for item in top_items[:5]:
            open_str = f"开板{item['open_times']}次" if item["open_times"] > 0 else "未开板"
            field_label = f"{item['name']}({item['code']})"
            field_value = f"涨幅+{item['change_pct']:.2f}% {open_str}"
            card.add_field(field_label, field_value)
        if items_count > 5:
            card.add_note(f"共 {items_count} 条记录，仅展示前 5 条")
        return card

    @staticmethod
    def news_card(
        title: str,
        message: str,
        items_count: int,
        top_items: list[dict[str, Any]],
    ) -> CardMessage:
        card = CardMessage(title=title, header_color="blue")
        card.add_text(message)
        card.add_separator()
        for item in top_items[:5]:
            source_str = f" [{item['source']}]" if item["source"] else ""
            card.add_text(f"• {item['title']}{source_str}")
        if items_count > 5:
            card.add_note(f"共 {items_count} 条新闻，仅展示前 5 条")
        return card

    @staticmethod
    def screen_result_card(
        title: str,
        message: str,
        items: list[dict[str, Any]],
    ) -> CardMessage:
        card = CardMessage(title=title, header_color="purple")
        card.add_text(message)
        card.add_separator()
        for item in items:
            ret20 = item.get("return_20d_pct")
            ret20_text = f"20日 {ret20:+.2f}%" if ret20 is not None else "20日 -"
            hot_tags = item.get("hot_tags") or []
            hotspot_text = f" [{' / '.join(hot_tags)}]" if hot_tags else ""
            card.add_field(
                f"{item['name']}({item['symbol']})",
                f"{ret20_text}{hotspot_text} {item['match_reason']}",
            )
        card.add_note("输入 /analyze <代码> 可继续查看单只股票分析")
        return card

    @staticmethod
    def watchlist_result_card(
        title: str,
        message: str,
        items: list[dict[str, Any]],
    ) -> CardMessage:
        card = CardMessage(title=title, header_color="blue")
        card.add_text(message)
        card.add_separator()
        for item in items:
            card.add_field(
                item["name"],
                (
                    f"来源 {item['source']} · {item['auto_refresh']} · 共 {item['count']} 只\n"
                    f"最近刷新 {item['last_refreshed_at']}\n{item['params']}"
                ),
            )
        return card

    # -- internal helpers --

    @staticmethod
    def _build_header(card: CardMessage) -> dict[str, Any]:
        if not card.title:
            return {}
        template = FeishuCardBuilder._color_to_template(card.header_color)
        return {
            "title": {"tag": "plain_text", "content": card.title},
            "template": template,
        }

    @staticmethod
    def _build_elements(card: CardMessage) -> list[dict[str, Any]]:
        elements: list[dict[str, Any]] = []
        for elem in card.elements:
            etype = elem.get("type")
            if etype == "text":
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": elem["content"]},
                })
            elif etype == "field":
                elements.append({
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {
                                "tag": "lark_md",
                                "content": f"**{elem['label']}**\n{elem['value']}",
                            },
                        }
                    ],
                })
            elif etype == "separator":
                elements.append({"tag": "hr"})
            elif etype == "button":
                button: dict[str, Any] = {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": elem["label"]},
                    "type": FeishuCardBuilder._button_style(elem.get("style", "default")),
                    "value": {"action": elem["value"]},
                }
                elements.append({"tag": "action", "actions": [button]})
            elif etype == "note":
                elements.append({
                    "tag": "note",
                    "elements": [{"tag": "plain_text", "content": elem["content"]}],
                })
        return elements

    @staticmethod
    def _color_to_template(color: str) -> str:
        mapping = {
            "blue": "blue",
            "green": "green",
            "red": "red",
            "orange": "orange",
            "purple": "violet",
            "grey": "grey",
        }
        return mapping.get(color, "blue")

    @staticmethod
    def _button_style(style: str) -> str:
        mapping = {
            "primary": "primary",
            "default": "default",
            "danger": "danger",
        }
        return mapping.get(style, "default")
