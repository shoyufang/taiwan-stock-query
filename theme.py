"""
主題系統 — 5 種配色主題 + CSS 注入
"""
import streamlit as st

THEMES = {
    "🌅 Claude 暖橘": {
        "bg":           "#F2F0EB",
        "sidebar":      "#E8E4DC",
        "surface":      "#FFFFFF",
        "primary":      "#D97757",
        "primary_dark": "#BF6340",
        "text":         "#1A1A1A",
        "text2":        "#6B6B6B",
        "border":       "#D8D4CB",
        "border_light": "#EAE7E0",
        "shadow":       "rgba(0,0,0,0.08)",
        "glow":         "rgba(217,119,87,0.20)",
        "hover_tint":   "rgba(217,119,87,0.06)",
        "checkbox_tint":"rgba(217,119,87,0.08)",
    },
    "🌊 深海藍": {
        "bg":           "#0F172A",
        "sidebar":      "#1E293B",
        "surface":      "#1E293B",
        "primary":      "#3B82F6",
        "primary_dark": "#2563EB",
        "text":         "#F1F5F9",
        "text2":        "#94A3B8",
        "border":       "#334155",
        "border_light": "#1E293B",
        "shadow":       "rgba(0,0,0,0.35)",
        "glow":         "rgba(59,130,246,0.25)",
        "hover_tint":   "rgba(59,130,246,0.08)",
        "checkbox_tint":"rgba(59,130,246,0.10)",
    },
    "🟢 翡翠綠": {
        "bg":           "#111827",
        "sidebar":      "#1F2937",
        "surface":      "#1F2937",
        "primary":      "#10B981",
        "primary_dark": "#059669",
        "text":         "#F9FAFB",
        "text2":        "#9CA3AF",
        "border":       "#374151",
        "border_light": "#1F2937",
        "shadow":       "rgba(0,0,0,0.40)",
        "glow":         "rgba(16,185,129,0.25)",
        "hover_tint":   "rgba(16,185,129,0.08)",
        "checkbox_tint":"rgba(16,185,129,0.10)",
    },
    "🟣 科技紫": {
        "bg":           "#0D0D1A",
        "sidebar":      "#1A1A2E",
        "surface":      "#1A1A2E",
        "primary":      "#8B5CF6",
        "primary_dark": "#7C3AED",
        "text":         "#E2E8F0",
        "text2":        "#A78BFA",
        "border":       "#2D2D4E",
        "border_light": "#1A1A2E",
        "shadow":       "rgba(0,0,0,0.50)",
        "glow":         "rgba(139,92,246,0.25)",
        "hover_tint":   "rgba(139,92,246,0.08)",
        "checkbox_tint":"rgba(139,92,246,0.10)",
    },
    "🥇 奢華黑金": {
        "bg":           "#1C1917",
        "sidebar":      "#292524",
        "surface":      "#292524",
        "primary":      "#F59E0B",
        "primary_dark": "#D97706",
        "text":         "#FAFAF9",
        "text2":        "#A8A29E",
        "border":       "#44403C",
        "border_light": "#292524",
        "shadow":       "rgba(0,0,0,0.45)",
        "glow":         "rgba(245,158,11,0.25)",
        "hover_tint":   "rgba(245,158,11,0.08)",
        "checkbox_tint":"rgba(245,158,11,0.10)",
    },
}

def inject_theme_css(theme_name: str):
    """根據主題名稱注入對應的 CSS 變數與全域樣式（單一 st.markdown 呼叫）"""
    t = THEMES.get(theme_name, THEMES["🌅 Claude 暖橘"])
    glow        = t["glow"]
    hover_tint  = t["hover_tint"]
    cb_tint     = t["checkbox_tint"]
    primary     = t["primary"]
    primary_dk  = t["primary_dark"]
    bg          = t["bg"]
    sidebar     = t["sidebar"]
    surface     = t["surface"]
    text        = t["text"]
    text2       = t["text2"]
    border      = t["border"]
    border_l    = t["border_light"]
    shadow      = t["shadow"]

    st.markdown(f"""
<style>
/* ═══════════════════════════════════════════════════════════
   台股查詢工具 — 設計系統（動態主題：{theme_name}）
   ═══════════════════════════════════════════════════════════ */

:root {{
    --claude-bg:           {bg};
    --claude-sidebar:      {sidebar};
    --claude-surface:      {surface};
    --claude-primary:      {primary};
    --claude-primary-dark: {primary_dk};
    --claude-text:         {text};
    --claude-text-2:       {text2};
    --claude-border:       {border};
    --claude-border-light: {border_l};
    --claude-shadow:       {shadow};
    --text-color:                  {text} !important;
    --background-color:            {bg} !important;
    --secondary-background-color:  {sidebar} !important;
    --primary-color:               {primary} !important;
}}

.stApp {{
    background-color: {bg} !important;
    color: {text} !important;
}}
[data-testid="stAppViewContainer"] {{
    background-color: {bg} !important;
}}
[data-testid="stHeader"] {{
    background-color: {bg} !important;
}}
[data-testid="stMain"] {{
    background-color: {bg} !important;
}}

p, span, div, li, td, th, pre, code,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] div,
[data-testid="stText"],
[data-testid="stCaptionContainer"],
.stMarkdown, .stText,
[class*="stMarkdown"], [class*="stText"] {{
    color: {text} !important;
}}

label, [data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
[data-baseweb="label"],
[data-baseweb="checkbox"] label {{
    color: {text} !important;
}}

[data-baseweb="select"] [data-baseweb="value"],
[data-baseweb="select"] span,
[data-baseweb="menu"] li {{
    color: {text} !important;
    background-color: {surface} !important;
}}

[data-testid="stRadio"] label,
[data-testid="stToggle"] label {{
    color: {text} !important;
}}

[data-testid="stNumberInput"] input {{
    color: {text} !important;
    background-color: {surface} !important;
}}

[data-testid="stSlider"] [data-testid="stMarkdownContainer"] p {{
    color: {text} !important;
}}

html, body, [class*="css"] {{
    font-family: 'Inter','Segoe UI',-apple-system,sans-serif;
    color: {text};
}}
.block-container {{ padding-top: 1.4rem !important; }}
h1 {{ font-size: 1.45rem !important; margin-bottom: 0 !important; font-weight: 700 !important; letter-spacing: -0.02em; color: {text} !important; }}
h2 {{ font-size: 1.1rem !important; font-weight: 600 !important; color: {text} !important; }}
h3 {{ font-size: 0.95rem !important; font-weight: 600 !important; color: {text} !important; }}
h4, h5, h6 {{ color: {text} !important; }}

[data-testid="stSidebar"] {{
    width: 250px !important;
    background-color: var(--claude-sidebar) !important;
    border-right: 1px solid var(--claude-border) !important;
}}
[data-testid="stSidebar"] .stButton button {{
    width: 100%;
    border-radius: 8px !important;
    font-size: 0.86rem !important;
    padding: 7px 14px !important;
    text-align: left !important;
    transition: all 0.15s ease !important;
    border: 1px solid var(--claude-border) !important;
    background: {surface}99 !important;
    color: var(--claude-text) !important;
    box-shadow: 0 1px 3px var(--claude-shadow) !important;
    margin-bottom: 3px !important;
}}
[data-testid="stSidebar"] .stButton button:hover {{
    background: var(--claude-surface) !important;
    border-color: var(--claude-primary) !important;
    box-shadow: 0 2px 8px {glow} !important;
    transform: translateY(-1px) !important;
}}
[data-testid="stSidebar"] .stButton button:active {{
    transform: translateY(0) !important;
}}
[data-testid="stSidebar"] .stButton button[kind="primary"] {{
    background: var(--claude-primary) !important;
    color: #fff !important;
    border-color: var(--claude-primary) !important;
    box-shadow: 0 2px 8px {glow} !important;
}}

[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 12px !important;
    border: 1px solid var(--claude-border) !important;
    background: var(--claude-surface) !important;
    box-shadow: 0 1px 4px var(--claude-shadow) !important;
}}

[data-testid="stCaptionContainer"] p {{
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.09em !important;
    text-transform: uppercase !important;
    color: var(--claude-text-2) !important;
    margin-bottom: 2px !important;
}}

[data-testid="stCheckbox"] {{ margin: 1px 0 !important; }}
[data-testid="stCheckbox"] label {{
    font-size: 0.84rem !important;
    padding: 3px 8px 3px 4px !important;
    border-radius: 6px !important;
    transition: background 0.12s !important;
    color: var(--claude-text) !important;
}}
[data-testid="stCheckbox"] label:hover {{ background: {cb_tint} !important; }}

button[kind="primary"] {{
    background: linear-gradient(135deg, var(--claude-primary) 0%, var(--claude-primary-dark) 100%) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 9px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    letter-spacing: 0.02em !important;
    box-shadow: 0 2px 10px {glow} !important;
    transition: all 0.15s ease !important;
}}
button[kind="primary"]:hover {{
    box-shadow: 0 4px 18px {glow} !important;
    transform: translateY(-1px) !important;
}}
button[kind="primary"]:active {{ transform: translateY(0) !important; }}

button[kind="secondary"] {{
    border-radius: 6px !important;
    font-size: 0.73rem !important;
    padding: 2px 10px !important;
    border: 1px solid var(--claude-border) !important;
    color: var(--claude-text-2) !important;
    background: var(--claude-surface) !important;
    transition: all 0.12s ease !important;
}}
button[kind="secondary"]:hover {{
    border-color: var(--claude-primary) !important;
    color: var(--claude-primary) !important;
    background: {hover_tint} !important;
}}

[data-testid="stTextInput"] input,
[data-testid="stDateInput"] input {{
    border-radius: 8px !important;
    border: 1px solid var(--claude-border) !important;
    font-size: 0.87rem !important;
    background: var(--claude-surface) !important;
    color: var(--claude-text) !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}}
[data-testid="stTextInput"] input:focus,
[data-testid="stDateInput"] input:focus {{
    border-color: var(--claude-primary) !important;
    box-shadow: 0 0 0 3px {glow} !important;
}}

[data-testid="stSelectbox"] [data-baseweb="select"] > div {{
    border-radius: 8px !important;
    border-color: var(--claude-border) !important;
    font-size: 0.87rem !important;
    background: var(--claude-surface) !important;
}}

[data-testid="stSlider"] [role="slider"] {{
    background: var(--claude-primary) !important;
    border-color: var(--claude-primary) !important;
}}

[data-testid="stProgressBar"] > div > div > div > div {{
    background: linear-gradient(90deg, var(--claude-primary), var(--claude-primary-dark)) !important;
}}

[data-testid="stExpander"] {{
    border-radius: 10px !important;
    border: 1px solid var(--claude-border) !important;
    background: var(--claude-surface) !important;
    box-shadow: 0 1px 3px var(--claude-shadow) !important;
    margin-bottom: 8px !important;
    overflow: hidden !important;
}}
[data-testid="stExpander"] summary {{
    font-size: 0.87rem !important;
    font-weight: 600 !important;
    padding: 10px 14px !important;
    border-radius: 10px !important;
    transition: background 0.12s !important;
    color: var(--claude-text) !important;
}}
[data-testid="stExpander"] summary:hover {{ background: {hover_tint} !important; }}

hr {{ border: none !important; border-top: 1px solid var(--claude-border) !important; margin: 1rem 0 !important; }}

[data-testid="stMetric"] {{
    background: var(--claude-surface) !important;
    border: 1px solid var(--claude-border) !important;
    border-radius: 10px !important;
    padding: 12px 16px !important;
    box-shadow: 0 1px 4px var(--claude-shadow) !important;
}}
[data-testid="stMetricLabel"] p {{ font-size: 0.73rem !important; color: var(--claude-text-2) !important; font-weight: 500 !important; }}
[data-testid="stMetricValue"] div {{ font-size: 1.4rem !important; font-weight: 700 !important; color: var(--claude-text) !important; }}

[data-testid="stDataFrame"] {{
    border-radius: 8px !important;
    overflow: hidden !important;
    border: 1px solid var(--claude-border) !important;
}}

[data-testid="stInfo"]    {{ border-radius: 8px !important; border-left: 3px solid #3b82f6 !important; }}
[data-testid="stWarning"] {{ border-radius: 8px !important; border-left: 3px solid #f59e0b !important; }}
[data-testid="stError"]   {{ border-radius: 8px !important; border-left: 3px solid #ef4444 !important; }}
[data-testid="stSuccess"] {{ border-radius: 8px !important; border-left: 3px solid #10b981 !important; }}

[data-testid="stChatInput"] {{
    border-radius: 12px !important;
    border: 1px solid {border} !important;
    background-color: transparent !important;
}}
[data-testid="stChatInput"] div,
[data-testid="stChatInput"] label,
.stChatInput div {{
    background-color: {surface} !important;
    color: {text} !important;
    border-color: {border} !important;
}}
[data-testid="stChatInput"] textarea {{
    font-size: 0.95rem !important;
    background-color: transparent !important;
    color: {text} !important;
    -webkit-text-fill-color: {text} !important;
}}
[data-testid="stChatInput"] textarea::placeholder,
[data-testid="stChatInput"] textarea::-webkit-input-placeholder {{
    color: {text2} !important;
    opacity: 0.8 !important;
    -webkit-text-fill-color: {text2} !important;
}}
[data-testid="stChatInput"] button {{
    color: {primary} !important;
    background-color: transparent !important;
}}
[data-testid="stChatMessage"] {{
    border-radius: 12px !important;
    padding: 4px 0 !important;
}}
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] span,
[data-testid="stChatMessage"] div {{
    color: {text} !important;
}}

[data-testid="stTabs"] [role="tab"] {{
    font-size: 0.86rem !important;
    font-weight: 500 !important;
    color: var(--claude-text-2) !important;
    border-radius: 8px 8px 0 0 !important;
    transition: color 0.12s !important;
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    color: var(--claude-primary) !important;
    border-bottom-color: var(--claude-primary) !important;
    font-weight: 600 !important;
}}
[data-testid="stTabs"] [role="tab"]:hover {{
    color: var(--claude-primary) !important;
    background: {hover_tint} !important;
}}
</style>

<!-- 鍵盤快捷鍵 -->
<script>
document.addEventListener('keydown', function(e) {{
    // Ctrl+K: 聚焦搜尋框
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {{
        e.preventDefault();
        var searchInput = document.querySelector('input[aria-label="🔍 快速搜尋"]') ||
                          document.querySelector('input[placeholder*="快速搜尋"]');
        if (searchInput) searchInput.focus();
    }}
    // Ctrl+S: 聚焦書籤名稱
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {{
        e.preventDefault();
        var bookmarkInput = document.querySelector('input[aria-label="快速書籤名稱"]') ||
                            document.querySelector('input[placeholder*="書籤"]');
        if (bookmarkInput) bookmarkInput.focus();
    }}
    // Escape: 清除搜尋
    if (e.key === 'Escape') {{
        var searchInput = document.querySelector('input[aria-label="🔍 快速搜尋"]');
        if (searchInput && searchInput.value) {{
            searchInput.value = '';
            searchInput.blur();
        }}
    }}
}});
</script>
""", unsafe_allow_html=True)
