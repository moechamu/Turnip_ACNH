import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import timedelta
import os
import requests
import json

# ページ設定はクラス外の冒頭で行うのがベスト
st.set_page_config(page_title="Turnip Trader Pro", layout="wide", initial_sidebar_state="expanded")

class TurnipView:
    def __init__(self):
        # CSS設定
        st.markdown("""
        <style>
        /* 全体の背景 */
        .stApp { background-color: #0e1117; }
        
        /* 基本の文字色（全体） */
        body, p, span, div {
            color: #dddddd;
        }

        .stNumberInput { margin-bottom: 0px; }
        
        /* 確率表示ボックス */
        .prob-box {
            padding: 15px;
            border-radius: 8px;
            background-color: #1e1e1e;
            margin-bottom: 20px;
            text-align: center;
            border: 1px solid #333;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .prob-confirmed {
            color: #00ff00;
            font-size: 1.8em;
            font-weight: bold;
            text-shadow: 0 0 15px rgba(0,255,0,0.5);
        }
        .prob-item {
            display: inline-block;
            margin: 5px 15px;
            font-size: 1.1em;
            font-family: 'Courier New', monospace;
            font-weight: 600;
        }

        /* ----------------------------------------------------------------- */
        /* コンポーネント単位のカラー調整 */
        /* ----------------------------------------------------------------- */

        /* 1. 具体的な入力Widgetのラベル文字色 (メイン画面用) */
        .stDateInput label p,
        .stNumberInput label p,
        .stSelectbox label p,
        .stTextInput label p {
            color: #dddddd !important;
            font-weight: 600 !important;
        }

        /* 2. Metric (来週の確率) のラベルと値 */
        div[data-testid="stMetricLabel"] p {
            color: #dddddd !important;
        }
        div[data-testid="stMetricValue"] div {
            color: #dddddd !important;
            font-weight: bold !important;
        }
        div[data-testid="stMetricDelta"],
        div[data-testid="stMetricDelta"] div,
        div[data-testid="stMetricDelta"] svg {
            color: #00ff00 !important;
            fill: #00ff00 !important;
        }

        /* 3. Expander (基本設定) */
        div[data-testid="stExpander"] details {
            border-color: #444 !important;
            border-radius: 5px;
        }
        div[data-testid="stExpander"] details summary {
            background-color: #1e1e1e !important;
            border: 1px solid #444 !important;
            color: #dddddd !important;
        }
        div[data-testid="stExpander"] details summary:hover {
            border-color: #00ff00 !important;
            color: #00ff00 !important;
        }
        div[data-testid="stExpander"] details summary:hover * {
            color: #00ff00 !important;
            fill: #00ff00 !important;
        }
        div[data-testid="stExpander"] details summary:focus,
        div[data-testid="stExpander"] details summary:active {
            background-color: #1e1e1e !important;
            color: #dddddd !important;
        }
        div[data-testid="stExpander"] details summary:focus *,
        div[data-testid="stExpander"] details summary:active * {
            color: #dddddd !important;
        }

        /* 4. プルダウン（Selectbox）の選択肢リスト（展開時） */
        ul[data-testid="stSelectboxVirtualDropdown"] li span,
        ul[data-testid="stSelectboxVirtualDropdown"] li div {
            color: #000000 !important;
        }
        ul[data-testid="stSelectboxVirtualDropdown"] {
            background-color: #ffffff !important;
        }
        
        /* 5. セレクトボックス本体（選択中の値） */
        div[data-testid="stSelectbox"] div[data-baseweb="select"] span,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] div {
            color: #000000 !important;
        }
        div[data-testid="stSelectbox"] svg {
            fill: #000000 !important;
            color: #000000 !important;
        }

        /* ---------------------------------------------------- */
        /* ★ここが今回の追加修正★ サイドバー（Sidebar）専用設定     */
        /* ---------------------------------------------------- */
        
        /* サイドバー内のあらゆる文字（見出し、ラベル、pタグ）を濃いグレーにする */
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] div,
        section[data-testid="stSidebar"] label {
            color: #333333 !important;
        }
        
        /* サイドバー内の入力欄の文字色も黒くする */
        section[data-testid="stSidebar"] .stNumberInput input {
            color: #333333 !important;
        }
        
        /* サイドバー内のプラス・マイナスボタンの色も見えるように調整 */
        section[data-testid="stSidebar"] button {
            color: #333333 !important;
        }

        /* ---------------------------------------------------- */
        /* Expander内のボタン */
        /* ---------------------------------------------------- */
        div[data-testid="stExpander"] .stButton button {
            background-color: #262730 !important;
            color: #dddddd !important;
            border: 1px solid #555 !important;
        }
        div[data-testid="stExpander"] .stButton button p {
            color: #dddddd !important;
        }
        div[data-testid="stExpander"] .stButton button:hover {
            border-color: #00ff00 !important;
            color: #00ff00 !important;
        }
        div[data-testid="stExpander"] .stButton button:hover p {
            color: #00ff00 !important;
        }
        </style>
        """, unsafe_allow_html=True)

    def display_input_form(self, current_confirmed_pattern=None):
        """基本設定と入力フォーム"""
        
        # --- 初期値管理 ---
        if 'base_date' not in st.session_state:
            today = pd.to_datetime("today")
            idx = (today.weekday() + 1) % 7 
            st.session_state['base_date'] = today - timedelta(days=idx)

        if 'buy_price' not in st.session_state: st.session_state['buy_price'] = 100
        if 'last_pattern' not in st.session_state: st.session_state['last_pattern'] = '不明'
        
        # inputキーの初期化
        for i in range(6):
            if f"input_{i}_0" not in st.session_state: st.session_state[f"input_{i}_0"] = 0
            if f"input_{i}_1" not in st.session_state: st.session_state[f"input_{i}_1"] = 0

        def reset_callback():
            # 1. 保存用データの収集
            current_date = st.session_state['base_date']
            buy_price = st.session_state['buy_price']
            
            # 確定パターン (キャッシュがあればそれを採用、なければ'不明')
            pattern = st.session_state.get('confirmed_pattern_cache')
            if pattern is None:
                pattern = '不明'
            
            # 月AM〜土PMの売値をリスト化 (合計12要素の一括データ)
            prices_list = []
            for i in range(6):
                prices_list.append(st.session_state[f"input_{i}_0"]) # AM
                prices_list.append(st.session_state[f"input_{i}_1"]) # PM
            
            # GASに送るためのJSONデータ構造を作成
            payload = {
                "date": current_date.strftime('%Y-%m-%d'),
                "buy_price": buy_price,
                "pattern": pattern,
                "prices": prices_list
            }

            try:
                gas_url = st.secrets["GAS_URL"]
                # 通信タイムアウトを設定 (念のため)
                response = requests.post(gas_url, data=json.dumps(payload), timeout=10)
                
                if response.status_code == 200:
                    st.toast(f"データをクラウドに保存して次週へ進みました 💾", icon="✅")
                else:
                    st.warning(f"保存に失敗しました (Status: {response.status_code})。入力値のリセットのみ実行します。")
            except Exception as e:
                # ネットワークエラーなどの場合
                st.error(f"クラウド保存中にエラーが発生しました: {e}")

            # 3. 次の週へのリセット処理 (既存のロジックを最適化)
            # 今週の日曜日に7日足して「来週の日曜日」にする
            st.session_state['base_date'] = current_date + timedelta(days=7)

            # 「先週のパターン」として、今回の確定パターンを引き継ぐ
            st.session_state['last_pattern'] = pattern

            # 画面上の入力欄をリセット (買値はデフォルト100、売値は0に)
            st.session_state['buy_price'] = 100
            for i in range(6):
                st.session_state[f'input_{i}_0'] = 0
                st.session_state[f'input_{i}_1'] = 0
            
            # 確定パターンキャッシュもクリア
            st.session_state['confirmed_pattern_cache'] = None
        
        # --- 1. 基本設定 (Expander) ---
        with st.expander("⚙️ 基本設定 / 次の週へ", expanded=True):
            c1, c2, c3 = st.columns([2, 1, 2])
            with c1:
                base_date = st.date_input(
                    "今週の日曜日", 
                    key='base_date',
                    min_value=pd.to_datetime("2000-01-01"),
                    max_value=pd.to_datetime("2100-12-31")
                )
            with c2:
                buy_price = st.number_input("日曜 買値", min_value=0, max_value=200, key='buy_price')
            with c3:
                last_pattern = st.selectbox("先週のパターン", ['不明', '波型', '跳ね小', '跳ね大', '減少'], key='last_pattern')
            
            st.button("Next Week ⏩ (保存して次週へ)", on_click=reset_callback, width='stretch')

        # --- 2. カブ価入力 (Sidebar) ---
        st.sidebar.header("📈 Price Input")
        st.sidebar.caption("午前/午後のカブ価を入力 (0は空白)")
        
        prices = {}
        days = ["月", "火", "水", "木", "金", "土"]
        
        for i, day in enumerate(days):
            cols = st.sidebar.columns([1, 1])
            with cols[0]:
                val_am = st.number_input(f"{day} AM", min_value=0, max_value=660, key=f"input_{i}_0")
                prices[f"{i}_0"] = val_am
            with cols[1]:
                val_pm = st.number_input(f"{day} PM", min_value=0, max_value=660, key=f"input_{i}_1")
                prices[f"{i}_1"] = val_pm

        return {'base_date': base_date, 'buy_price': buy_price, 'last_pattern': last_pattern, 'prices': prices}

    def display_chart(self, result_dict):
        """Plotlyチャート描画"""
        st.subheader(f"📊 Price Prediction Analysis")
        
        df = result_dict.get('plot_data')
        probs = result_dict.get('probabilities')
        confirmed = result_dict.get('confirmed_pattern')

        # --- 確率表示エリア ---
        if probs:
            if confirmed:
                st.markdown(f'<div class="prob-box"><span class="prob-confirmed">{confirmed} 100% 🎯</span></div>', unsafe_allow_html=True)
            else:
                prob_html = ""
                sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
                for p_name, p_val in sorted_probs:
                    if p_val > 0.1:
                        color = "#777"
                        if p_val >= 90: color = "#00ff00"
                        elif p_val >= 50: color = "#ff4b4b"
                        elif p_val >= 20: color = "#ffbb00"
                        elif p_val >= 10: color = "#00ccff"
                        prob_html += f'<span class="prob-item" style="color:{color}">{p_name}: {p_val:.1f}%</span>'
                st.markdown(f'<div class="prob-box">{prob_html}</div>', unsafe_allow_html=True)

        if df is None or df.empty:
            st.warning("⚠️ 入力値に矛盾があります。数値を再確認してください。")
            return

        # Plotly Graph Objects
        fig = go.Figure()

        # 1. 範囲の塗りつぶし (Min〜Max)
        fig.add_trace(go.Scatter(
            x=df['label'], y=df['max_price'],
            mode='lines',
            line=dict(width=0),
            showlegend=False, hoverinfo='skip'
        ))
        fig.add_trace(go.Scatter(
            x=df['label'], y=df['min_price'],
            mode='lines',
            line=dict(width=0),
            fill='tonexty', 
            fillcolor='rgba(0, 255, 0, 0.15)',
            showlegend=False, hoverinfo='skip'
        ))

        # 2. 線の描画
        fig.add_trace(go.Scatter(
            x=df['label'], y=df['max_price'],
            mode='lines+markers', name='最高値',
            line=dict(color='#00ff00', width=1, dash='dot'),
            marker=dict(size=3)
        ))
        fig.add_trace(go.Scatter(
            x=df['label'], y=df['min_price'],
            mode='lines+markers', name='最低値',
            line=dict(color='#ff00ff', width=1, dash='dot'),
            marker=dict(size=3)
        ))
        fig.add_trace(go.Scatter(
            x=df['label'], y=df['avg_price'],
            mode='lines', name='平均予測',
            line=dict(color='#00ccff', width=2),
            hoverinfo='y'
        ))

        if 'buy_price' in df.columns:
            bp = df['buy_price'].iloc[0]
            fig.add_trace(go.Scatter(
                x=df['label'], y=[bp]*len(df),
                mode='lines', name=f'買値 ({bp})',
                line=dict(color='#ff6347', width=1, dash='dash'),
                hoverinfo='name'
            ))

        fig.add_trace(go.Scatter(
            x=df['label'], y=df['actual_price'],
            mode='lines+markers', name='実績値',
            line=dict(color='#ffffff', width=3),
            marker=dict(size=8, color='#ffffff', symbol='circle', line=dict(width=2, color='#333'))
        ))
        
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)',
            
            # 全体の文字色
            font=dict(color='#dddddd'),
            
            # 凡例（レジェンド）の文字色を個別に強制指定
            legend=dict(
                orientation="h", 
                yanchor="bottom", 
                y=1.02, 
                xanchor="right", 
                x=1,
                font=dict(color='#dddddd') # ここで色を指定
            ),
            
            xaxis=dict(title=None, type='category', fixedrange=True),
            yaxis=dict(title="ベル", fixedrange=True, gridcolor='#333'),
            height=450,
            margin=dict(l=20, r=20, t=30, b=20),
            hovermode="x unified"
        )
        st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})

    def display_summary(self, result_dict, base_date, matrix_df):
        """推奨アクションと共有テキスト"""
        
        df = result_dict.get('plot_data')
        
        probs = result_dict.get('probabilities')
        
        if df is None or df.empty: return

        st.markdown("---") 
        c1, c2 = st.columns([3, 2])
        
        # --- 戦略表示 ---
        with c1:
            st.subheader("⚡ Trade Strategy")
            max_val = df['max_price'].max()
            best_rows = df[df['max_price'] == max_val]
            
            if not best_rows.empty:
                best_time = best_rows.iloc[0]['label']
                best_price = int(max_val)
            else:
                best_time, best_price = "---", 0
            
            st.markdown(f"""
            <div style="
                background: linear-gradient(90deg, #1f1f23 0%, #111 100%);
                border-left: 5px solid #00ff00; border-radius: 4px;
                padding: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.5);
                display: flex; justify-content: space-between; align-items: center;
            ">
                <div>
                    <p style="color:#888; font-size:0.8rem; margin:0; letter-spacing:1px;">OPTIMAL EXIT</p>
                    <p style="color:#fff; font-size:2rem; margin:0; font-weight:700;">{best_time}</p>
                </div>
                <div style="text-align:right;">
                    <p style="color:#00ff00; font-size:2.5rem; margin:0; font-weight:700; font-family:monospace;">{best_price}<span style="font-size:1rem; color:#aaa;"> Bells</span></p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # --- 共有テキスト生成 ---
        with c2:
            st.subheader("📤 Share")
            next_sunday = base_date + pd.Timedelta(days=7)
            next_sunday = next_sunday.strftime("%m/%d")
            this_week_str = base_date.strftime("%m/%d")
            
            # 最有力パターン
            prob_text = "不明"
            if probs:
                top = sorted(probs.items(), key=lambda x: x[1], reverse=True)[0]
                prob_text = f"{top[0]}({top[1]:.0f}%)"
            
            # 来週の確率
            try:
                probs_dict = matrix_df.iloc[0].to_dict()
                sorted_next = sorted(probs_dict.items(), key=lambda x: x[1], reverse=True)
                next_txt = " / ".join([f"{k}:{v*100:.0f}%" for k, v in sorted_next if v > 0.1][:2])
            except:
                next_txt = "計算中..."

            share_text = f"【あつ森カブ価 {this_week_str}週】\n現在: {prob_text}\n最大: {best_price}ベル ({best_time})\n次の日曜日: {next_sunday}\n来週: {next_txt}\n"
            st.text_area("Copy this:", share_text, height=100)

    def display_prediction_table(self, result_dict):
        """詳細テーブル"""
        table_df = result_dict.get('table_df')
        if table_df is None or table_df.empty: return

        st.markdown("---")
        with st.expander("📅 詳細データテーブルを見る", expanded=True): # 見やすいように開いておく
            
            # --- ハイライト処理用関数の定義 ---
            def highlight_max_cells(row):
                # 行ごとのスタイルリストを初期化（デフォルトはスタイルなし）
                styles = ['' for _ in row.index]
                
                # 1. その行の「限界値（最大値）」を取得
                try:
                    row_max = int(row['限界値'])
                except:
                    return styles # 取得できなければ何もしない

                # 売り時がない（0ベル等）の場合はスキップ
                if row_max <= 0: return styles

                # 2. 月曜AM〜土曜PMのカブ価カラムをチェック
                # DAYS_LABELは ['日AM', '月AM'...] なのでインデックス1以降を見る
                days_cols = ['月AM', '月PM', '火AM', '火PM', '水AM', '水PM', 
                             '木AM', '木PM', '金AM', '金PM', '土AM', '土PM']
                
                for col in days_cols:
                    if col not in row.index: continue
                    
                    cell_val_str = str(row[col])
                    upper_val = 0
                    
                    # セルの値 ("90" や "90〜140") から最大値を抽出
                    if "〜" in cell_val_str:
                        try:
                            # "min〜max" の max部分を取る
                            _, u = cell_val_str.split("〜")
                            upper_val = int(u)
                        except: pass
                    else:
                        try:
                            # 単一数値の場合
                            upper_val = int(cell_val_str)
                        except: pass
                    
                    # 3. セルの最大値が、行の限界値と一致すれば赤太字にする
                    if upper_val == row_max:
                        # そのカラムのインデックスを取得してスタイルを設定
                        idx = row.index.get_loc(col)
                        # 色はStreamlitの赤(#ff4b4b)を使用せず、濃い赤色
                        styles[idx] = 'color: #a12b13; font-weight: bold;'
                
                return styles

            # --- スタイルの適用 ---
            # axis=1 で行ごとに処理を適用
            styler = table_df.style.apply(highlight_max_cells, axis=1)

            st.dataframe(
                styler,
                width='stretch',
                hide_index=True,
                column_config={
                    "パターン": st.column_config.TextColumn("Pattern", width="small"),
                    "確率": st.column_config.ProgressColumn("Prob", format="%.2f%%", min_value=0, max_value=100),
                    "最低値": st.column_config.NumberColumn("Min", format="%d"),
                    "限界値": st.column_config.NumberColumn("Max", format="%d"),
                },
                height=400
            )


    def display_matrix(self, df_matrix, title="Probability Matrix"):
        """確率行列"""
        if df_matrix is None or df_matrix.empty: return
        
        st.markdown(f"**{title}**")
        probs_dict = df_matrix.iloc[0].to_dict()
        
        cols = st.columns(len(probs_dict))
        for i, (k, v) in enumerate(probs_dict.items()):
            val_pct = v * 100
            
            # 20%を超えていたらdelta引数を使って緑色にする演出
            # delta_color="normal" は、プラス(文字列でも)なら緑、マイナスなら赤になる
            delta_val = "有力" if val_pct > 20 else None
            
            cols[i].metric(
                label=k, 
                value=f"{val_pct:.1f}%", 
                delta=delta_val
            )