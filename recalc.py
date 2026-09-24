def recalculate_database_macros():
    data = load_data()
    changed = False
    
    # Yeni eklenecek olan protein tozu vs takviyelerin macro karsiliklari
    sup_macros = {
        'Protein Tozu (Takviye)': {'kcal': 120, 'pro': 24, 'carb': 3, 'fat': 1}
    }
    
    for uid, user in data.items():
        if "daily" in user and "meals" in user["daily"]:
            new_kcal = 0; new_pro = 0; new_carbs = 0; new_fats = 0
            for meal in user["daily"]["meals"]:
                fname = meal.get("food", "").lower()
                mult = meal.get("mult", 1)
                
                food_data = FOODS.get(fname)
                
                # Ozel case for hardcoded supps
                if not food_data and meal.get("food") in sup_macros:
                    food_data = sup_macros[meal.get("food")]
                
                if food_data:
                    meal["kcal"] = round(food_data.get("kcal", 0) * mult)
                    meal["pro"] = round(food_data.get("pro", 0) * mult)
                    new_kcal += meal["kcal"]
                    new_pro += meal["pro"]
                    new_carbs += round(food_data.get("carb", 0) * mult)
                    new_fats += round(food_data.get("fat", 0) * mult)
                else:
                    new_kcal += meal.get("kcal", 0)
                    new_pro += meal.get("pro", 0)
                    new_carbs += meal.get("carb", 0)
                    new_fats += meal.get("fat", 0)
                    
            user["daily"]["kcal"] = new_kcal
            user["daily"]["protein"] = new_pro
            user["daily"]["carbs"] = new_carbs
            user["daily"]["fats"] = new_fats
            changed = True
            
        if "history" in user:
            for d, dayData in user["history"].items():
                if "meals" in dayData and isinstance(dayData["meals"], list):
                    new_h_kcal = 0; new_h_pro = 0
                    for meal in dayData["meals"]:
                        fname = meal.get("food", "").lower()
                        mult = meal.get("mult", 1)
                        food_data = FOODS.get(fname)
                        if not food_data and meal.get("food") in sup_macros:
                            food_data = sup_macros[meal.get("food")]
                            
                        if food_data:
                            meal["kcal"] = round(food_data.get("kcal", 0) * mult)
                            meal["pro"] = round(food_data.get("pro", 0) * mult)
                            new_h_kcal += meal["kcal"]
                            new_h_pro += meal["pro"]
                        else:
                            new_h_kcal += meal.get("kcal", 0)
                            new_h_pro += meal.get("pro", 0)
                    dayData["kcal"] = new_h_kcal
                    dayData["protein"] = new_h_pro
                    changed = True
                    
    if changed:
        save_data(data)
        print("Veritabani makrolari foods.json ile guncellendi!")
