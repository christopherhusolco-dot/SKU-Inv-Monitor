APP_CSS = """
<style>
    :root {
        --navy-950: #07182a;
        --navy-900: #0b2035;
        --navy-800: #12324d;
        --blue-600: #1677ff;
        --blue-100: #eaf3ff;
        --ink: #172b4d;
        --muted: #667085;
        --line: #e5eaf0;
        --surface: #f4f7fb;
        --white: #ffffff;
        --red: #d92d20;
        --amber: #dc6803;
        --green: #16865b;
    }

    html, body, [class*="css"] { font-family: Inter, "Segoe UI", Arial, sans-serif; }
    .stApp, [data-testid="stAppViewContainer"] { background: var(--surface); color: var(--ink); }
    .block-container { max-width: 1580px; padding: 1.15rem 1.7rem 2.4rem; }
    [data-testid="stHeader"] { background: rgba(244,247,251,.88); }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--navy-950) 0%, var(--navy-900) 100%);
        border-right: 0;
    }
    [data-testid="stSidebar"] > div:first-child { padding-top: .55rem; }
    [data-testid="stSidebar"] .stRadio > label,
    [data-testid="stSidebar"] .stCaptionContainer,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: #aebfd0 !important; }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
        padding: .56rem .7rem;
        margin: .14rem 0;
        border-radius: 9px;
        color: #d8e4ef;
        transition: background .12s ease;
    }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover {
        background: rgba(255,255,255,.075);
    }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:has(input:checked) {
        background: #1769d2;
        color: #ffffff;
        box-shadow: 0 5px 18px rgba(0,70,170,.22);
    }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label > div:first-child { display: none; }
    .sidebar-brand {
        padding: .8rem .45rem 1.2rem;
        border-bottom: 1px solid rgba(255,255,255,.10);
        margin-bottom: .9rem;
    }
    .brand-mark {
        display: inline-flex;
        width: 36px;
        height: 36px;
        align-items: center;
        justify-content: center;
        border-radius: 10px;
        background: #1677ff;
        color: #fff;
        font-size: 19px;
        margin-right: .55rem;
        vertical-align: middle;
    }
    .brand-name {
        color: #ffffff;
        font-size: 1.05rem;
        font-weight: 760;
        letter-spacing: -.02em;
        vertical-align: middle;
    }
    .brand-subtitle { color: #91a8bd; font-size: .74rem; margin: .55rem 0 0 2.9rem; }
    .sidebar-label {
        color: #7992aa;
        font-size: .68rem;
        font-weight: 760;
        letter-spacing: .10em;
        text-transform: uppercase;
        margin: 1rem .45rem .45rem;
    }
    .source-list { margin: .1rem .3rem .7rem; padding: .15rem .2rem; }
    .source-item {
        display: flex;
        align-items: flex-start;
        gap: .48rem;
        color: #d3dfeb;
        font-size: .77rem;
        line-height: 1.25;
        padding: .31rem .18rem;
    }
    .source-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #35c98a;
        box-shadow: 0 0 0 3px rgba(53,201,138,.12);
        margin-top: .25rem;
        flex: 0 0 auto;
    }
    .source-dot.missing { background: #f97066; box-shadow: 0 0 0 3px rgba(249,112,102,.12); }
    .excluded-source {
        border: 1px solid rgba(255,255,255,.10);
        border-radius: 9px;
        color: #91a8bd;
        font-size: .71rem;
        line-height: 1.35;
        padding: .62rem .7rem;
        margin: .65rem .45rem 0;
        background: rgba(255,255,255,.035);
    }
    .excluded-source strong { color: #c7d6e4; }

    .app-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
        margin: .05rem 0 .9rem;
    }
    .app-header h1 {
        color: var(--navy-900);
        font-size: 1.78rem;
        line-height: 1.15;
        letter-spacing: -.035em;
        margin: 0 0 .32rem;
    }
    .app-header p { color: var(--muted); font-size: .89rem; margin: 0; }
    .header-badges {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: .4rem;
        padding-top: .2rem;
    }
    .header-badge {
        border: 1px solid #d8e1ea;
        background: #fff;
        color: #44566c;
        border-radius: 999px;
        padding: .34rem .68rem;
        font-size: .72rem;
        white-space: nowrap;
    }
    .header-badge.live { color: #067647; border-color: #abefc6; background: #ecfdf3; }
    .header-badge.live::before {
        content: "";
        display: inline-block;
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #17b26a;
        margin-right: .38rem;
        vertical-align: middle;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--line) !important;
        border-radius: 12px !important;
        background: #ffffff;
        box-shadow: 0 1px 2px rgba(16,24,40,.025);
    }
    div[data-baseweb="select"] > div,
    [data-testid="stTextInput"] input { border-color: #d9e1e9; background: #fff; }
    [data-testid="stWidgetLabel"] p { color: #526174; font-size: .74rem; font-weight: 650; }

    .section-title {
        color: var(--navy-900);
        font-size: 1rem;
        font-weight: 760;
        letter-spacing: -.015em;
        margin: .45rem 0 .52rem;
    }
    .section-subtitle { color: var(--muted); font-size: .77rem; margin: -.3rem 0 .55rem; }
    .kpi-card {
        min-height: 112px;
        background: #fff;
        border: 1px solid var(--line);
        border-top: 3px solid #7aa7d9;
        border-radius: 12px;
        padding: .82rem .88rem .72rem;
        box-shadow: 0 1px 2px rgba(16,24,40,.035);
    }
    .kpi-card.risk { border-top-color: #e5484d; }
    .kpi-card.warn { border-top-color: #f5a524; }
    .kpi-card.good { border-top-color: #35a56f; }
    .kpi-label {
        color: #677489;
        font-size: .71rem;
        font-weight: 700;
        line-height: 1.2;
        text-transform: uppercase;
        letter-spacing: .035em;
    }
    .kpi-value {
        color: var(--navy-900);
        font-size: 1.52rem;
        font-weight: 780;
        line-height: 1.15;
        letter-spacing: -.035em;
        margin: .42rem 0 .27rem;
        white-space: nowrap;
    }
    .kpi-foot { color: #8995a5; font-size: .68rem; line-height: 1.25; }
    .team-card {
        min-height: 116px;
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 11px;
        padding: .78rem .82rem;
    }
    .team-card .team-name { color: #1769d2; font-weight: 740; font-size: .78rem; margin-bottom: .45rem; }
    .team-card .team-value { color: var(--navy-900); font-size: 1.08rem; font-weight: 770; letter-spacing: -.02em; }
    .team-card .team-note { color: #7b8797; font-size: .68rem; line-height: 1.3; margin-top: .3rem; }
    .callout {
        background: #eef6ff;
        border: 1px solid #cfe3fb;
        border-left: 4px solid #1677ff;
        border-radius: 10px;
        color: #29445f;
        padding: .75rem .9rem;
        margin: .25rem 0 .75rem;
        font-size: .82rem;
    }
    .callout.risk { background: #fff5f4; border-color: #fecdca; border-left-color: #d92d20; }
    .callout.good { background: #f0fbf5; border-color: #c9efda; border-left-color: #16865b; }
    div[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
    .small-note { color: var(--muted); font-size: .76rem; }
    h2, h3 { color: var(--navy-900); letter-spacing: -.02em; }
    .stButton > button, .stDownloadButton > button {
        border-radius: 8px;
        border-color: #cbd5df;
        font-weight: 650;
    }
    .stButton > button[kind="primary"] { background: #1769d2; border-color: #1769d2; }

    @media (max-width: 980px) {
        .app-header { display: block; }
        .header-badges { justify-content: flex-start; margin-top: .65rem; }
        .kpi-card { min-height: 102px; }
        .block-container { padding-left: 1rem; padding-right: 1rem; }
    }
</style>
"""
