import streamlit as st
from model import TurnipModel
from view import TurnipView

class TurnipController:
    def __init__(self):
        # モデルとビューの初期化
        self.model = TurnipModel()
        self.view = TurnipView()

    def run(self):
        # 1. 前回の計算で確定したパターンがあれば取得（リセット時のデフォルト値用）
        confirmed_cache = st.session_state.get('confirmed_pattern_cache', None)

        # 2. View: 入力フォームの表示と入力値の取得
        user_input = self.view.display_input_form(current_confirmed_pattern=confirmed_cache)
        
        # 3. Model: 予測計算の実行
        # input: {base_date, buy_price, last_pattern, prices}
        prediction_result = self.model.predict(user_input)
        
        # 4. Controller: 計算結果から「確定パターン」があればキャッシュに保存
        # これにより、ユーザーが「Next Week」を押したときに、確定したパターンが自動的に「先週のパターン」になる
        new_confirmed = prediction_result.get('confirmed_pattern')
        st.session_state['confirmed_pattern_cache'] = new_confirmed
        
        # 5. Model: 来週の遷移確率（Matrix）の取得
        if new_confirmed:
            matrix_title = f"来週のパターン確率 （今週が「{new_confirmed}」の場合）"
            matrix_df = self.model.get_transition_matrix(new_confirmed)
        else:
            # まだ確定していない場合は「不明」として確率を出す（あるいは現在の最も高い確率を使うなど改良可）
            matrix_title = "来週のパターン確率 （今週が不明なため平均値）"
            matrix_df = self.model.get_transition_matrix("不明")
        
        # 6. View: 結果の表示
        self.view.display_chart(prediction_result)
        self.view.display_summary(prediction_result, user_input['base_date'], matrix_df)
        self.view.display_matrix(matrix_df, title=matrix_title)
        self.view.display_prediction_table(prediction_result)