import csv
import math
import os
from datetime import datetime
from collections import defaultdict, Counter

class CSAORecommender:
    def __init__(self, restaurants_file='restaurants.csv', menu_file='menu_items.csv', orders_file='orders.csv', users_file='users.csv'):
        self.restaurants = {}
        self.menu_by_res = {}
        self.all_items = {}
        
        self.item_frequencies = Counter()
        self.co_occurrence = defaultdict(Counter)
        self.user_history = defaultdict(Counter) 
        self.user_personas = {} 
        self.users = []
        self.orders_file = orders_file
        
        self._load_data(restaurants_file, menu_file, users_file)
        self._train_from_history()

    def _load_data(self, restaurants_file, menu_file, users_file):
        with open(restaurants_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                self.restaurants[row['res_id']] = row
                self.menu_by_res[row['res_id']] = []

        with open(menu_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                res_id = row['res_id']
                if res_id not in self.menu_by_res:
                    self.menu_by_res[res_id] = []
                    self.restaurants[res_id] = {'cuisine': 'Universal'}
                
                row['price'] = float(row['price'])
                row['is_veg'] = row['is_veg'].lower() == 'true'
                row['popularity_score'] = 0.0 
                row['cuisine'] = row['cuisine'] 
                
                self.menu_by_res[res_id].append(row)
                self.all_items[row['item_id']] = row
                
        try:
            with open(users_file, 'r', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    self.users.append(row)
        except FileNotFoundError: pass

    def _train_from_history(self):
        try:
            with open(self.orders_file, 'r', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    user_id = row['user_id']
                    items_in_cart = row['item_ids'].split('|')
                    for item in items_in_cart:
                        self.item_frequencies[item] += 1
                        self.user_history[user_id][item] += 1 
                        for other_item in items_in_cart:
                            if item != other_item:
                                self.co_occurrence[item][other_item] += 1
                                
            self._recalculate_popularity()
            self._calculate_user_personas()
        except FileNotFoundError: pass

    def _calculate_user_personas(self):
        for user, item_counts in self.user_history.items():
            cat_counts = defaultdict(int)
            total_items = 0
            for item_id, count in item_counts.items():
                if item_id in self.all_items:
                    cat = self.all_items[item_id]['category']
                    cat_counts[cat] += count
                    total_items += count
            
            if total_items > 0:
                if (cat_counts['dessert'] / total_items) > 0.25:
                    self.user_personas[user] = 'Sweet Tooth'
                elif (cat_counts['starter'] + cat_counts['street_food']) / total_items > 0.35:
                    self.user_personas[user] = 'Snacker'
                elif (cat_counts['main_gravy'] + cat_counts['main_biryani'] + cat_counts['chinese_main']) / total_items > 0.40:
                    self.user_personas[user] = 'Heavy Eater'
                else:
                    self.user_personas[user] = 'Balanced'

    def _recalculate_popularity(self):
        if self.item_frequencies:
            max_freq = max(self.item_frequencies.values())
            for item_id, freq in self.item_frequencies.items():
                if item_id in self.all_items:
                    self.all_items[item_id]['popularity_score'] = round(freq / max_freq, 2)

    def save_order(self, user_id, res_id, item_ids, total_amount):
        order_id = f"ord_realtime_{int(datetime.now().timestamp())}"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        items_str = "|".join(item_ids)
        
        file_exists = os.path.isfile(self.orders_file)
        with open(self.orders_file, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['order_id', 'user_id', 'res_id', 'timestamp', 'total_amount', 'item_ids'])
            writer.writerow([order_id, user_id, res_id, timestamp, total_amount, items_str])

        for item in item_ids:
            self.item_frequencies[item] += 1
            self.user_history[user_id][item] += 1
            for other_item in item_ids:
                if item != other_item:
                    self.co_occurrence[item][other_item] += 1
        
        self._recalculate_popularity()
        self._calculate_user_personas() 

    def get_users(self):
        return self.users[:10] 

    def get_feed(self, user_id=None, current_hour=14, current_month=3, limit=2000):
        pref_cuisine = None
        user_segment = 'Regular' 
        
        if user_id:
            user_obj = next((u for u in self.users if u['user_id'] == user_id), None)
            if user_obj:
                pref_cuisine = user_obj['pref_cuisine']
                user_segment = user_obj.get('segment', 'Regular')
        
        user_persona = self.user_personas.get(user_id, 'Balanced')

        scored_feed = []
        for item in self.all_items.values():
            base_score = item['popularity_score'] * 100 
            cat = item['category']
            price = item['price']
            
            # merchandising
            if cat == 'combo': base_score *= 2.5
            elif cat in ['main_biryani', 'main_gravy', 'chinese_main']: base_score *= 2.0
            elif cat in ['starter', 'street_food']: base_score *= 1.5
            elif cat in ['dessert', 'beverage']: base_score *= 1.2
            elif cat in ['bread', 'accompaniment_salan']: base_score *= 0.8 
            elif cat == 'accompaniment_dip': base_score *= 0.05 

            # user prefs
            if pref_cuisine and item['cuisine'] == pref_cuisine:
                base_score *= 1.8 
            
            if user_persona == 'Sweet Tooth' and cat == 'dessert': base_score *= 1.5
            elif user_persona == 'Snacker' and cat in ['starter', 'street_food']: base_score *= 1.5
            elif user_persona == 'Heavy Eater' and cat in ['main_gravy', 'main_biryani']: base_score *= 1.5

            # segment elasticity
            if user_segment == 'Premium':
                if price >= 250: base_score *= 1.6 
            elif user_segment == 'Budget':
                if price <= 150: base_score *= 1.6 
                elif price >= 300: base_score *= 0.7 
            elif user_segment == 'Regular':
                if 120 <= price <= 280: base_score *= 1.3 

            # temporal heuristics
            if 6 <= current_hour <= 11: 
                if cat == 'beverage' and ('Coffee' in item['name'] or 'Tea' in item['name']): base_score *= 2.0
                if cat == 'street_food': base_score *= 1.3
            elif 12 <= current_hour <= 16: 
                if cat in ['main_gravy', 'main_biryani', 'chinese_main', 'combo']: base_score *= 1.5
                if cat == 'beverage' and ('Lassi' in item['name'] or 'Mojito' in item['name']): base_score *= 1.5
            elif current_hour >= 21 or current_hour <= 2: 
                if cat == 'dessert': base_score *= 1.8
                if cat == 'street_food' or cat == 'starter': base_score *= 1.5

            item_copy = item.copy()
            item_copy['feed_score'] = base_score
            item_copy['res_name'] = self.restaurants[item['res_id']]['name']
            scored_feed.append(item_copy)

        scored_feed.sort(key=lambda x: x['feed_score'], reverse=True)
        return scored_feed[:limit]

    def _calculate_content_affinity(self, name1, name2):
        n1, n2 = name1.lower(), name2.lower()
        affinity = 0
        if 'chocolate' in n1 and ('coffee' in n2 or 'chocolate' in n2 or 'brownie' in n2): affinity += 50
        if 'coffee' in n1 and ('brownie' in n2 or 'cake' in n2): affinity += 50
        if ('fries' in n1 or 'burger' in n1) and 'coke' in n2: affinity += 50
        return affinity

    def get_recommendations(self, cart_item_ids, res_id, user_id=None, current_hour=14, current_month=3):
        if not cart_item_ids or res_id not in self.menu_by_res: return []

        cart = [self.all_items[i] for i in cart_item_ids if i in self.all_items]
        cart_ids = set(cart_item_ids)
        cart_value = sum(i['price'] for i in cart)
        last_item = cart[-1]
        
        cart_categories = set(i['category'] for i in cart)
        is_only_dessert = all(c == 'dessert' for c in cart_categories)
        is_only_beverage = all(c == 'beverage' for c in cart_categories)

        raw_candidates = [item for item in self.menu_by_res[res_id] if item['item_id'] not in cart_ids]
        valid_candidates = []
        seen_names = set([i['name'] for i in cart])
        
        for cand in raw_candidates:
            if cand['name'] in seen_names: continue
            if is_only_dessert and cand['category'] not in ['dessert', 'beverage']: continue
            seen_names.add(cand['name'])
            valid_candidates.append(cand)

        user_persona = self.user_personas.get(user_id, 'Balanced')
        
        user_segment = 'Regular'
        if user_id:
            user_obj = next((u for u in self.users if u['user_id'] == user_id), None)
            if user_obj: user_segment = user_obj.get('segment', 'Regular')

        scored_candidates = []
        for cand in valid_candidates:
            tie_breaker = (hash(cand['item_id']) % 10) / 10.0 
            score = (cand['popularity_score'] * 10) + tie_breaker
            reason = "Trending"

            # 1. temporal
            if 6 <= current_hour <= 11:
                if cand['category'] in ['beverage', 'street_food']:
                    score += 80; reason = "Morning kickstart"
            elif 12 <= current_hour <= 16:
                if cand['category'] == 'beverage' and ('Lassi' in cand['name'] or 'Mojito' in cand['name'] or 'Coke' in cand['name']):
                    score += 80; reason = "Refreshing afternoon pick"
            elif current_hour >= 21 or current_hour <= 2:
                if cand['category'] == 'dessert' or 'Pizza' in cand['name'] or cand['category'] == 'starter':
                    score += 80; reason = "Late night craving"
                    
            is_summer = current_month in [3, 4, 5, 6, 7]
            if is_summer and cand['category'] == 'beverage' and ('Cold' in cand['name'] or 'Lassi' in cand['name'] or 'Mojito' in cand['name']):
                score += 50; reason = "Beat the heat"

            # 2. nlp and segment mapping
            content_boost = self._calculate_content_affinity(last_item['name'], cand['name'])
            if content_boost > 0:
                score += content_boost
                reason = "Pairs perfectly"

            if user_segment == 'Premium' and cand['price'] >= 250: score += 50
            elif user_segment == 'Budget' and cand['price'] <= 150: score += 50

            # 3. user hist
            if user_id and user_id in self.user_history:
                if self.user_history[user_id][cand['item_id']] > 0:
                    score += 300
                    reason = "Your usual order"

            # 4. co-occurrence matrix evaluation
            max_prob = 0
            for cart_item in cart:
                cid = cart_item['item_id']
                cand_id = cand['item_id']
                if self.item_frequencies[cid] > 0:
                    prob = self.co_occurrence[cid][cand_id] / self.item_frequencies[cid]
                    if prob > max_prob: max_prob = prob
            
            if max_prob > 0.05: 
                score += (max_prob * 2000) 
                reason = "Frequently bought together"

            # 5. bounds
            price_ratio = cand['price'] / max(cart_value, 1)
            if price_ratio > 0.8: score -= (math.log(price_ratio + 1) * 100)

            if score > 0: 
                cand_copy = cand.copy()
                cand_copy['score'] = score
                cand_copy['reason'] = reason
                scored_candidates.append(cand_copy)

        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        return scored_candidates[:8]

    def get_upsell(self, cart_item_ids, res_id):
        if not cart_item_ids or res_id not in self.menu_by_res: return []
        cart = [self.all_items[i] for i in cart_item_ids if i in self.all_items]
        cart_ids = set(cart_item_ids)
        
        candidates = [item for item in self.menu_by_res[res_id] if item['item_id'] not in cart_ids]
        candidates.sort(key=lambda x: x['popularity_score'], reverse=True)
        if candidates:
            upsell_item = candidates[0].copy()
            upsell_item['discounted_price'] = int(upsell_item['price'] * 0.8) 
            return [upsell_item]
        return []