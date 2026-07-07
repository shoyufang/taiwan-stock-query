"""
永豐金 Shioaji 專屬渲染元件（2026-07-07 從 ui_components.py 拆出）
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go


def render_shioaji_snapshot(df: pd.DataFrame):
    """渲染 Shioaji 快照與最佳五檔 HTML/CSS 視覺化面板"""
    if df.empty:
        st.warning("沒有快照數據")
        return

    def _parse_list(val):
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            import ast
            try:
                return ast.literal_eval(val)
            except:
                try:
                    return [float(x.strip()) for x in val.replace("[", "").replace("]", "").split(",") if x.strip()]
                except:
                    return []
        return []

    # 對於每一檔股票進行渲染
    for idx, row in df.iterrows():
        code = row["代號"]
        name = row["名稱"]
        close = row["收盤"]
        open_p = row["開盤"]
        high = row["最高"]
        low = row["最低"]
        change = row["漲跌"]
        change_rate = row["漲跌幅(%)"]
        vol = row["單量"]
        total_vol = row["總量"]

        # 決定顏色
        color = "#ff4b4b" if change > 0 else ("#00cc96" if change < 0 else "#888888")
        emoji = "📈" if change > 0 else ("📉" if change < 0 else "➖")

        with st.container(border=True):
            # 頂部即時快照卡
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <div>
                    <span style="font-size:20px; font-weight:bold; color:var(--claude-text);">{name} ({code})</span>
                    <span style="margin-left:8px; font-size:14px; color:var(--claude-text-2);">即時行情</span>
                </div>
                <div style="text-align:right;">
                    <span style="font-size:22px; font-weight:bold; color:{color};">{close}</span>
                    <span style="font-size:14px; font-weight:bold; color:{color}; margin-left:5px;">{emoji} {change:+.2f} ({change_rate:+.2f}%)</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 四格基本數據
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("開盤價", f"{open_p:.2f}" if isinstance(open_p, (int, float)) else str(open_p))
            c2.metric("最高 / 最低", f"{high:.2f} / {low:.2f}" if isinstance(high, (int, float)) and isinstance(low, (int, float)) else f"{high} / {low}")
            c3.metric("單筆成交量", f"{vol} 張" if isinstance(vol, (int, float)) else str(vol))
            c4.metric("今日總成交量", f"{total_vol} 張" if isinstance(total_vol, (int, float)) else str(total_vol))

            # 最佳五檔解析與呈現
            bid_ps = _parse_list(row.get("委買價", []))
            bid_vs = _parse_list(row.get("委買量", []))
            ask_ps = _parse_list(row.get("委賣價", []))
            ask_vs = _parse_list(row.get("委賣量", []))

            if bid_ps and ask_ps:
                # 委買賣十檔總量
                total_order_vol = sum(bid_vs) + sum(ask_vs)
                if total_order_vol == 0:
                    total_order_vol = 1

                # 掛單比率計算與條形圖 (委買紅色，委賣綠色)
                ask_data = []
                for i in range(min(5, len(ask_ps))):
                    ask_data.append((ask_ps[i], ask_vs[i]))
                ask_data = ask_data[::-1] # 委賣五到委賣一

                bid_data = []
                for i in range(min(5, len(bid_ps))):
                    bid_data.append((bid_ps[i], bid_vs[i]))

                html = f"""
                <div style="background-color:var(--claude-surface); border-radius:10px; padding:15px; border: 1px solid var(--claude-border); font-family:monospace; max-width:600px; margin:15px auto 0 auto;">
                    <div style="text-align:center; font-weight:bold; color:var(--claude-text-2); border-bottom:1px solid var(--claude-border); padding-bottom:8px; margin-bottom:8px; display:flex; justify-content:space-between;">
                        <span style="width:30%; text-align:left;">委買量(張)</span>
                        <span style="width:40%; text-align:center;">最佳五檔報價</span>
                        <span style="width:30%; text-align:right;">委賣量(張)</span>
                    </div>
                """

                # 1. 委賣
                for ap, av in ask_data:
                    pct = (av / total_order_vol) * 100
                    html += f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; height:24px; margin-bottom:4px;">
                        <span style="width:30%; text-align:left; color:var(--claude-text-2);">-</span>
                        <span style="width:40%; text-align:center; color:#00cc96; font-weight:bold;">{ap:.2f}</span>
                        <div style="width:30%; display:flex; align-items:center; justify-content:flex-end;">
                            <span style="margin-right:8px; font-weight:bold; color:#00cc96;">{av}</span>
                            <div style="width:60px; background-color:var(--claude-border-light); height:8px; border-radius:4px; overflow:hidden;">
                                <div style="width:{pct:.1f}%; background-color:#00cc96; height:100%;"></div>
                            </div>
                        </div>
                    </div>
                    """

                # 2. 成交價
                html += f"""
                <div style="text-align:center; margin: 8px 0; border-top:1px dashed var(--claude-border); border-bottom:1px dashed var(--claude-border); padding:6px 0; background-color:var(--claude-bg);">
                    <span style="color:var(--claude-text-2); font-weight:bold; font-size:12px;">最新成交價</span>
                    <span style="color:{color}; font-weight:bold; font-size:18px; margin-left:10px;">{close:.2f}</span>
                </div>
                """

                # 3. 委買
                for bp, bv in bid_data:
                    pct = (bv / total_order_vol) * 100
                    html += f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; height:24px; margin-top:4px;">
                        <div style="width:30%; display:flex; align-items:center; justify-content:flex-start;">
                            <div style="width:60px; background-color:var(--claude-border-light); height:8px; border-radius:4px; overflow:hidden; margin-right:8px;">
                                <div style="width:{pct:.1f}%; background-color:#ff4b4b; height:100%;"></div>
                            </div>
                            <span style="font-weight:bold; color:#ff4b4b;">{bv}</span>
                        </div>
                        <span style="width:40%; text-align:center; color:#ff4b4b; font-weight:bold;">{bp:.2f}</span>
                        <span style="width:30%; text-align:right; color:var(--claude-text-2);">-</span>
                    </div>
                    """

                html += "</div>"
                st.markdown(html, unsafe_allow_html=True)
            else:
                st.info("⚠️ 盤後或未提供最佳五檔價量資料。")


def render_shioaji_contract(df: pd.DataFrame):
    """渲染官方合約細節 (Glassmorphic 名冊)"""
    if df.empty:
        st.warning("無合約資訊。")
        return
    st.markdown("### 📜 證券官方合約與交易限制明細")

    with st.container(border=True):
        col1, col2 = st.columns(2)
        c_dict = dict(zip(df["屬性"], df["官方設定值"]))

        with col1:
            st.markdown(f"**股票代號：** `{c_dict.get('股票代號', 'N/A')}`")
            st.markdown(f"**股票名稱：** `{c_dict.get('股票名稱', 'N/A')}`")
            st.markdown(f"**上市市場/交易所：** `{c_dict.get('交易所', 'N/A')}`")
            st.markdown(f"**產業類別：** `{c_dict.get('產業類別', 'N/A')}`")
            st.markdown(f"**現股當沖 / 資券互抵：** `{c_dict.get('現股當沖/資券互抵', 'N/A')}`")

        with col2:
            st.markdown(f"**是否可融資交易：** `{c_dict.get('是否可信用融資', 'N/A')}`")
            st.markdown(f"**是否可融券交易：** `{c_dict.get('是否可信用融券', 'N/A')}`")
            st.markdown(f"**融資成數/比率：** `{c_dict.get('融資成數/比率', 'N/A')}`")
            st.markdown(f"**融券保證金成數：** `{c_dict.get('融券保證金成數', 'N/A')}`")

        st.divider()

        c_ref, c_up, c_down = st.columns(3)
        c_ref.metric("昨日參考價", f"${c_dict.get('今日參考價', 'N/A')}")
        c_up.metric("🔴 今日漲停價", f"${c_dict.get('今日漲停價', 'N/A')}")
        c_down.metric("🟢 今日跌停價", f"${c_dict.get('今日跌停價', 'N/A')}")


def render_shioaji_big_orders(df_dict: dict):
    """渲染主力大單分析與資金流向圓餅圖"""
    summary = df_dict.get("summary", pd.DataFrame())
    detail = df_dict.get("detail", pd.DataFrame())

    if summary.empty:
        st.error("查無大單統計數據。")
        return

    sum_dict = dict(zip(summary["指標項目"], summary["數值"]))

    total_ticks = sum_dict.get("總成交筆數", 0)
    total_volume = sum_dict.get("總成交張數", 0)
    total_amount = sum_dict.get("總成交金額 (元)", 0.0)

    big_buy_cnt = sum_dict.get("主力大單買入筆數", 0)
    big_buy_vol = sum_dict.get("主力大單買入張數", 0)
    big_buy_amt = sum_dict.get("主力大單買入金額 (元)", 0.0)

    big_sell_cnt = sum_dict.get("主力大單賣出筆數", 0)
    big_sell_vol = sum_dict.get("主力大單賣出張數", 0)
    big_sell_amt = sum_dict.get("主力大單賣出金額 (元)", 0.0)

    net_buy_amt = sum_dict.get("主力大單淨流入金額 (元)", 0.0)
    big_pct = sum_dict.get("大單佔總成交金額比例(%)", 0.0)

    with st.container(border=True):
        st.markdown("### 📊 主力大單資金流向分析")

        c1, c2, c3 = st.columns(3)
        net_color = "#ff4b4b" if net_buy_amt > 0 else ("#00cc96" if net_buy_amt < 0 else "#888888")
        net_symbol = "➕" if net_buy_amt > 0 else ("" if net_buy_amt < 0 else "")

        c1.metric("主力大單買入總額", f"{big_buy_amt/10000:.1f} 萬元" if isinstance(big_buy_amt, (int, float)) else str(big_buy_amt), f"{big_buy_cnt} 筆")
        c2.metric("主力大單賣出總額", f"{big_sell_amt/10000:.1f} 萬元" if isinstance(big_sell_amt, (int, float)) else str(big_sell_amt), f"{big_sell_cnt} 筆")

        with c3:
            net_val_str = f"{net_symbol}{net_buy_amt/10000:.1f} 萬" if isinstance(net_buy_amt, (int, float)) else str(net_buy_amt)
            st.markdown(f"""
            <div style="background-color:#F8FAFC; padding:10px; border-radius:8px; border:1px solid #E2E8F0; text-align:center;">
                <span style="font-size:12px; color:#64748B; font-weight:bold;">主力大單淨流入</span><br/>
                <span style="font-size:22px; font-weight:bold; color:{net_color};">{net_val_str}</span>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        col_chart, col_detail = st.columns([1, 1])

        with col_chart:
            st.caption("🎯 大單佔總成交金額比例與資金方向")
            normal_amt = max(0.0, total_amount - big_buy_amt - big_sell_amt) if isinstance(total_amount, (int, float)) and isinstance(big_buy_amt, (int, float)) and isinstance(big_sell_amt, (int, float)) else 0.0

            labels = ["大單買入", "大單賣出", "一般成交"]
            values = [big_buy_amt, big_sell_amt, normal_amt]
            colors = ["#ff4b4b", "#00cc96", "#E2E8F0"]

            fig = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=.4,
                marker=dict(colors=colors),
                textinfo="percent+label"
            )])
            fig.update_layout(
                margin=dict(t=10, b=10, l=10, r=10),
                height=250,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            net_解读_str = "買方力道強勁，主力呈淨買超流入！" if isinstance(net_buy_amt, (int, float)) and net_buy_amt > 0 else "賣方力道沉重，主力呈淨賣出流出！"
            st.markdown(f"""
            <div style="background-color:#EFF6FF; border-left:4px solid #3B82F6; padding:10px; border-radius:4px; font-size:13px; color:#1E3A8A;">
                ℹ️ <b>籌碼解讀：</b>本交易日主力大單佔總成交金額 <b>{big_pct:.1f}%</b>。
                大單淨流入為 <b style="color:{net_color};">{net_val_str}</b>。<br/>
                {net_解读_str}
            </div>
            """, unsafe_allow_html=True)

        with col_detail:
            st.caption("📋 最新 50 筆大單明細")
            if not detail.empty and "說明" not in detail.columns:
                df_show = detail.copy()
                df_show["金額"] = df_show["金額"].apply(lambda x: f"{x/10000:.1f} 萬" if isinstance(x, (int, float)) else str(x))
                st.dataframe(df_show, use_container_width=True, hide_index=True)
            elif not detail.empty:
                st.write(detail)
            else:
                st.info("無達到門檻的大單資料。")
