import pandas as pd
import numpy as np
import math
from datetime import timedelta

class TurnipModel:
    def __init__(self):
        # ID順序: 0=波型, 1=跳ね大, 2=跳ね小, 3=減少
        self.PATTERN_NAMES = ['波型', '跳ね大', '跳ね小', '減少']
        self.DAYS_LABEL = ['日AM', '月AM', '月PM', '火AM', '火PM', '水AM', '水PM', 
                           '木AM', '木PM', '金AM', '金PM', '土AM', '土PM']
        
        # ピーク日特定用のラベルリスト
        self.PEAK_LABELS = ['月AM', '月PM', '火AM', '火PM', '水AM', '水PM', 
                            '木AM', '木PM', '金AM', '金PM', '土AM', '土PM']
        
        # 遷移確率テーブル
        self.TRANSITION_MATRIX = {
            '波型':   [0.20, 0.30, 0.35, 0.15],
            '跳ね大': [0.50, 0.05, 0.25, 0.20],
            '跳ね小': [0.45, 0.25, 0.15, 0.15],
            '減少':   [0.25, 0.45, 0.25, 0.05],
            '不明':   [0.25, 0.25, 0.25, 0.25] 
        }

    def predict(self, input_data):
        base_date = pd.to_datetime(input_data['base_date'])
        buy_price = input_data['buy_price']
        current_prices = self._parse_prices(input_data['prices'])
        last_pattern_input = input_data['last_pattern']

        min_buy = buy_price if buy_price > 0 else 90
        max_buy = buy_price if buy_price > 0 else 110
        range_len = max_buy - min_buy + 1
        
        trans_probs_dict = self.get_transition_probs(last_pattern_input)
        trans_probs = [trans_probs_dict[name] for name in self.PATTERN_NAMES]

        valid_scenarios = []

        for bp in range(min_buy, max_buy + 1):
            base_prob = 1.0 / range_len
            self._calc_pattern_0_wave(bp, current_prices, valid_scenarios, trans_probs[0] * base_prob)
            self._calc_pattern_1_large(bp, current_prices, valid_scenarios, trans_probs[1] * base_prob)
            self._calc_pattern_2_small(bp, current_prices, valid_scenarios, trans_probs[2] * base_prob)
            self._calc_pattern_3_dec(bp, current_prices, valid_scenarios, trans_probs[3] * base_prob)

        # --- 集計 ---
        result = {
            'probabilities': {},
            'confirmed_pattern': None,
            'table_df': pd.DataFrame(),
            'plot_data': None
        }

        if not valid_scenarios: return result

        total_mass = sum(s['mass'] for s in valid_scenarios)
        if total_mass == 0: return result

        # 確率正規化
        for s in valid_scenarios:
            s['prob_pct'] = (s['mass'] / total_mass) * 100

        type_probs = {name: 0.0 for name in self.PATTERN_NAMES}
        for s in valid_scenarios:
            type_probs[s['pattern_name']] += s['prob_pct']
        
        result['probabilities'] = type_probs
        
        for p_name, prob in type_probs.items():
            if prob > 99.9:
                result['confirmed_pattern'] = p_name
                break

        # --- テーブル作成 ---
        table_rows = []
        cols = ['パターン', '確率'] + self.DAYS_LABEL + ['最低値', '限界値']

        for p_name in self.PATTERN_NAMES:
            if type_probs[p_name] > 0:
                type_scenarios = [s for s in valid_scenarios if s['pattern_name'] == p_name]
                summary_row = self._aggregate_scenarios(type_scenarios, p_name, type_probs[p_name], current_prices, is_summary=True)
                table_rows.append(summary_row)
                
                subtypes = {}
                for s in type_scenarios:
                    lbl = s['sub_label']
                    if lbl not in subtypes: subtypes[lbl] = []
                    subtypes[lbl].append(s)
                
                day_order = {'月AM':0, '月PM':1, '火AM':2, '火PM':3, '水AM':4, '水PM':5, 
                             '木AM':6, '木PM':7, '金AM':8, '金PM':9, '土AM':10, '土PM':11, '通常':99}
                sorted_keys = sorted(subtypes.keys(), key=lambda x: day_order.get(x.split(' ')[0], 99))
                
                for sub_lbl in sorted_keys:
                    sub_list = subtypes[sub_lbl]
                    sub_prob = sum(s['prob_pct'] for s in sub_list)
                    detail_name = f" └ {sub_lbl}"
                    detail_row = self._aggregate_scenarios(sub_list, detail_name, sub_prob, current_prices, is_summary=False)
                    table_rows.append(detail_row)

        if table_rows:
            result['table_df'] = pd.DataFrame(table_rows, columns=cols)

        result['plot_data'] = self._prepare_plot_data(valid_scenarios, base_date, buy_price, current_prices)
        
        return result

    # ---------------------------------------------------------
    # 区間演算ロジック
    # ---------------------------------------------------------

    def _intceil(self, val):
        return int(val + 0.99999)

    def _get_price_range(self, base_price, min_r, max_r, offset=0):
        min_val = self._intceil(base_price * min_r) + offset
        max_val = self._intceil(base_price * max_r) + offset
        return [min_val, max_val]

    def _get_decay_ranges(self, base_price, length, start_rate_min, start_rate_max, dec_min, dec_max):
        ranges = []
        curr_min_rate = start_rate_min
        curr_max_rate = start_rate_max
        for _ in range(length):
            ranges.append([self._intceil(base_price * curr_min_rate), self._intceil(base_price * curr_max_rate)])
            curr_min_rate -= dec_max
            curr_max_rate -= dec_min
        return ranges

    def _check_ranges_strict(self, ranges, prices):
        for i in range(len(ranges)):
            if i >= 12: break
            p = prices[i]
            # 入力値が存在する場合のチェック
            if p > 0:
                if not (ranges[i][0] <= p <= ranges[i][1]):
                    return False
            
            # 論理的矛盾のチェック(最小値が最大値を超えている場合など)
            if ranges[i][0] > ranges[i][1]:
                return False
        return True

    # ---------------------------------------------------------
    # パターン生成
    # ---------------------------------------------------------

    # Pattern 0: 波型
    def _calc_pattern_0_wave(self, bp, prices, scenarios, prob):
        for dec1 in [2, 3]:
            dec2 = 5 - dec1
            for hi1 in range(0, 7):
                hi2_and_3 = 7 - hi1
                for hi3 in range(0, hi2_and_3 + 1):
                    hi2 = hi2_and_3 - hi3
                    sub_prob = prob / (2 * 7 * (hi2_and_3 + 1)) 
                    ranges = []
                    for _ in range(hi1): ranges.append(self._get_price_range(bp, 0.9, 1.4))
                    ranges.extend(self._get_decay_ranges(bp, dec1, 0.6, 0.8, 0.04, 0.10))
                    for _ in range(hi2): ranges.append(self._get_price_range(bp, 0.9, 1.4))
                    ranges.extend(self._get_decay_ranges(bp, dec2, 0.6, 0.8, 0.04, 0.10))
                    for _ in range(hi3): ranges.append(self._get_price_range(bp, 0.9, 1.4))
                    if self._check_ranges_strict(ranges, prices):
                        scenarios.append({
                            'pattern_idx': 0, 'pattern_name': '波型',
                            'sub_label': '通常', 'base_price': bp,
                            'mass': sub_prob, 'min_max': ranges[:12]
                        })

    # Pattern 1: 跳ね大 (Large Spike)
    def _calc_pattern_1_large(self, bp, prices, scenarios, prob):
        mass = prob / 7
        for peak_ninji in range(3, 10): 
            decreasing_len = peak_ninji - 2
            
            ranges = []
            ranges.extend(self._get_decay_ranges(bp, decreasing_len, 0.85, 0.9, 0.03, 0.05))
            
            # 急騰フェーズ
            ranges.append(self._get_price_range(bp, 0.9, 1.4))
            ranges.append(self._get_price_range(bp, 1.4, 2.0))
            ranges.append(self._get_price_range(bp, 2.0, 6.0)) # PEAK
            ranges.append(self._get_price_range(bp, 1.4, 2.0))
            ranges.append(self._get_price_range(bp, 0.9, 1.4))
            
            rest_len = 12 - len(ranges)
            for _ in range(rest_len): ranges.append(self._get_price_range(bp, 0.4, 0.9))
            
            if self._check_ranges_strict(ranges[:12], prices):
                peak_idx = peak_ninji
                peak_label = self.PEAK_LABELS[peak_idx] if peak_idx < 12 else "圏外"
                scenarios.append({
                    'pattern_idx': 1, 'pattern_name': '跳ね大',
                    'sub_label': peak_label,
                    'base_price': bp,
                    'mass': mass, 'min_max': ranges[:12]
                })

    # Pattern 2: 跳ね小 (Small Spike)
    def _calc_pattern_2_small(self, bp, prices, scenarios, prob):
        mass = prob / 8 
        # peak_ninji: 変調開始インデックス (2=月AM ... 9=木PM)
        for peak_ninji in range(2, 10): 
            decreasing_len = peak_ninji - 2
            
            ranges = []
            # 1. 減少フェーズ
            ranges.extend(self._get_decay_ranges(bp, decreasing_len, 0.4, 0.9, 0.03, 0.05))
            
            # 2. 上昇フェーズ (5回セット)
            # ranges[decreasing_len]   : Spike1 (0.9-1.4)
            # ranges[decreasing_len+1] : Spike2 (0.9-1.4)
            # ranges[decreasing_len+2] : Spike3 (1.4-2.0) -1  <- 対象1
            # ranges[decreasing_len+3] : Spike4 (1.4-2.0)     <- 頂点(Target)
            # ranges[decreasing_len+4] : Spike5 (1.4-2.0) -1  <- 対象2
            
            ranges.append(self._get_price_range(bp, 0.9, 1.4)) 
            ranges.append(self._get_price_range(bp, 0.9, 1.4))
            ranges.append(self._get_price_range(bp, 1.4, 2.0, -1)) 
            ranges.append(self._get_price_range(bp, 1.4, 2.0))     # PEAK
            ranges.append(self._get_price_range(bp, 1.4, 2.0, -1)) 
            
            # 3. 余り
            rest_len = 12 - len(ranges)
            if rest_len > 0:
                ranges.extend(self._get_decay_ranges(bp, rest_len, 0.4, 0.9, 0.03, 0.05))

            # 頂点(Spike4)の実測値がある場合のキャップ処理
            # 頂点(Spike4)のインデックスは「減少長 + 3」
            peak_idx = decreasing_len + 3
            
            if peak_idx < 12 and prices[peak_idx] > 0:
                # 頂点の実測値が入力されている場合
                actual_peak_price = prices[peak_idx]
                price_cap = actual_peak_price - 1
                
                # Spike3 (頂点の手前) の最大値をキャップ
                idx_prev = peak_idx - 1
                if idx_prev >= 0 and idx_prev < len(ranges):
                    ranges[idx_prev][1] = min(ranges[idx_prev][1], price_cap)
                
                # Spike5 (頂点の後) の最大値をキャップ
                idx_next = peak_idx + 1
                if idx_next < 12 and idx_next < len(ranges):
                    ranges[idx_next][1] = min(ranges[idx_next][1], price_cap)

            if self._check_ranges_strict(ranges[:12], prices):
                peak_idx_label = peak_ninji + 1
                peak_label = self.PEAK_LABELS[peak_idx_label] if peak_idx_label < 12 else "圏外"
                
                scenarios.append({
                    'pattern_idx': 2, 'pattern_name': '跳ね小',
                    'sub_label': peak_label,
                    'base_price': bp,
                    'mass': mass, 'min_max': ranges[:12]
                })

    # Pattern 3: 減少
    def _calc_pattern_3_dec(self, bp, prices, scenarios, prob):
        ranges = self._get_decay_ranges(bp, 12, 0.85, 0.9, 0.03, 0.05)
        if self._check_ranges_strict(ranges, prices):
            scenarios.append({
                'pattern_idx': 3, 'pattern_name': '減少',
                'sub_label': '通常', 'base_price': bp,
                'mass': prob, 'min_max': ranges
            })

    # ---------------------------------------------------------
    # ヘルパー
    # ---------------------------------------------------------
    def get_transition_probs(self, last_pattern):
        vals = self.TRANSITION_MATRIX.get(last_pattern, self.TRANSITION_MATRIX['不明'])
        return dict(zip(self.PATTERN_NAMES, vals))

    def get_transition_matrix(self, pattern_for_matrix):
        vals = self.TRANSITION_MATRIX.get(pattern_for_matrix, self.TRANSITION_MATRIX['不明'])
        return pd.DataFrame([vals], columns=self.PATTERN_NAMES, index=['確率'])

    def _aggregate_scenarios(self, scenarios, name, prob_pct, current_prices, is_summary=True):
        all_mins = np.array([s['min_max'] for s in scenarios])[:,:,0]
        all_maxs = np.array([s['min_max'] for s in scenarios])[:,:,1]
        type_min = all_mins.min(axis=0)
        type_max = all_maxs.max(axis=0)
        
        for i, val in enumerate(current_prices):
            if val > 0: type_min[i] = val; type_max[i] = val
        
        base_prices = [s['base_price'] for s in scenarios]
        sun_min = min(base_prices); sun_max = max(base_prices)
        period_min = min(type_min.min(), sun_min)
        period_max = max(type_max.max(), sun_max)
        
        display_name = f"【{name}】" if is_summary else name
        
        row = {
            'パターン': display_name, 
            '確率': prob_pct, 
            '最低値': period_min, 
            '限界値': period_max
        }
        
        row['日AM'] = f"{sun_min}" if sun_min == sun_max else f"{sun_min}〜{sun_max}"
        for i in range(12):
            col = self.DAYS_LABEL[i+1]
            mn = type_min[i]; mx = type_max[i]
            row[col] = f"{mn}" if mn == mx else f"{mn}〜{mx}"
        return row

    def _parse_prices(self, price_dict):
        arr = [0] * 12
        for key, val in price_dict.items():
            if "_" not in key: continue
            d, a = map(int, key.split('_'))
            if 0 <= d <= 5: arr[d*2 + a] = val
        return arr

    def _prepare_plot_data(self, valid_scenarios, base_date, buy_price, current_prices):
        global_mins = [999] * 13
        global_maxs = [0] * 13
        global_sums = [0] * 13
        
        for s in valid_scenarios:
            prob = s['prob_pct'] / 100.0
            bp = s['base_price']
            global_mins[0] = min(global_mins[0], bp)
            global_maxs[0] = max(global_maxs[0], bp)
            global_sums[0] += bp * prob
            
            for i in range(12):
                mn = s['min_max'][i][0]
                mx = s['min_max'][i][1]
                global_mins[i+1] = min(global_mins[i+1], mn)
                global_maxs[i+1] = max(global_maxs[i+1], mx)
                global_sums[i+1] += ((mn + mx) / 2) * prob

        plot_actuals = [None] * 13
        if buy_price > 0: 
            plot_actuals[0] = buy_price
            global_mins[0] = buy_price
            global_maxs[0] = buy_price
            
        for i, val in enumerate(current_prices):
            if val > 0:
                plot_actuals[i+1] = val
                global_mins[i+1] = val
                global_maxs[i+1] = val

        dates = []; labels = []
        dates.append(base_date); labels.append("日曜")
        days = ["月", "火", "水", "木", "金", "土"]
        for i, d in enumerate(days):
            date = base_date + timedelta(days=i+1)
            dates.append(date + timedelta(hours=9)); labels.append(f"{d} AM")
            dates.append(date + timedelta(hours=12)); labels.append(f"{d} PM")

        return pd.DataFrame({
            'datetime': dates,
            'label': labels,
            'min_price': global_mins,
            'max_price': global_maxs,
            'avg_price': global_sums,
            'actual_price': plot_actuals
        })