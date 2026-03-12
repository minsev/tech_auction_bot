from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ---------- Основные reply-меню ----------
def main_menu():
    kb = [
        [KeyboardButton(text="💰 Срочный выкуп")],
        [KeyboardButton(text="🔄 Я перекуп")],
        [KeyboardButton(text="🛍 Купить технику")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def user_menu():
    kb = [
        [KeyboardButton(text="💰 Создать заявку на выкуп")],
        [KeyboardButton(text="📋 Мои заявки")],
        [KeyboardButton(text="⭐ Избранное")],
        [KeyboardButton(text="🔔 Мои подписки")],
        [KeyboardButton(text="💸 Реферальная программа")],
        [KeyboardButton(text="💰 Мой кошелек")],
        [KeyboardButton(text="🛍 Купить технику")],
        [KeyboardButton(text="🆘 Техподдержка")],
        [KeyboardButton(text="🔙 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def reseller_menu():
    kb = [
        [KeyboardButton(text="📦 Заявки на выкуп")],
        [KeyboardButton(text="🏷 Мои объявления")],
        [KeyboardButton(text="➕ Создать объявление")],
        [KeyboardButton(text="📝 Мои отзывы")],
        [KeyboardButton(text="⭐ Избранное")],
        [KeyboardButton(text="📊 Моя статистика")],
        [KeyboardButton(text="🔔 Мои подписки")],
        [KeyboardButton(text="💸 Реферальная программа")],
        [KeyboardButton(text="💰 Мой кошелек")],
        [KeyboardButton(text="🛍 Купить технику")],
        [KeyboardButton(text="🆘 Техподдержка")],
        [KeyboardButton(text="🔙 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ---------- Инлайн-клавиатуры для выбора ----------

def categories_inline_keyboard():
    from database import get_categories
    categories = get_categories()
    builder = InlineKeyboardBuilder()
    for cat_id, cat_name in categories:
        builder.button(text=cat_name, callback_data=f"cat_{cat_id}")
    builder.adjust(2)
    return builder.as_markup()

def brands_inline_keyboard(category_id):
    from database import get_brands_by_category
    brands = get_brands_by_category(category_id)
    builder = InlineKeyboardBuilder()
    for brand_id, brand_name in brands:
        builder.button(text=brand_name, callback_data=f"brand_{brand_id}")
    builder.adjust(2)
    return builder.as_markup()

def models_inline_keyboard(brand_id):
    from database import get_models_by_brand
    models = get_models_by_brand(brand_id)
    builder = InlineKeyboardBuilder()
    for model_id, model_name in models:
        builder.button(text=model_name, callback_data=f"model_{model_id}")
    builder.adjust(2)
    return builder.as_markup()

def specs_inline_keyboard(model_id, spec_type, selected_specs=None):
    """
    spec_type: например 'color', 'storage'
    selected_specs: список ID выбранных характеристик (для мультивыбора)
    """
    from database import get_specs_by_model_and_type
    specs = get_specs_by_model_and_type(model_id, spec_type)
    if not specs:
        return None
    builder = InlineKeyboardBuilder()
    for spec_id, spec_value in specs:
        text = spec_value
        if selected_specs and spec_id in selected_specs:
            text = "✅ " + text
        builder.button(text=text, callback_data=f"spec_{spec_type}_{spec_id}")
    builder.button(text="➡️ Далее", callback_data="next")
    builder.adjust(2)
    return builder.as_markup()

def condition_inline_keyboard():
    builder = InlineKeyboardBuilder()
    conditions = ["Новое", "Как новое", "Б/у", "Требует ремонта"]
    for cond in conditions:
        builder.button(text=cond, callback_data=f"cond_{cond}")
    builder.adjust(2)
    return builder.as_markup()

def display_replaced_inline_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Да", callback_data="display_yes")
    builder.button(text="Нет", callback_data="display_no")
    builder.adjust(2)
    return builder.as_markup()

def defects_inline_keyboard():
    builder = InlineKeyboardBuilder()
    common_defects = ["Царапины", "Сколы", "Потертости", "Пятна на экране", "Другое"]
    for defect in common_defects:
        builder.button(text=defect, callback_data=f"defect_{defect}")
    builder.button(text="✅ Готово", callback_data="defect_done")
    builder.adjust(2)
    return builder.as_markup()

def accessories_inline_keyboard():
    builder = InlineKeyboardBuilder()
    acc = ["Зарядка", "Наушники", "Чехол", "Документы", "Коробка", "Другое"]
    for a in acc:
        builder.button(text=a, callback_data=f"acc_{a}")
    builder.button(text="✅ Готово", callback_data="acc_done")
    builder.adjust(2)
    return builder.as_markup()

# ---------- Клавиатуры для заявок и лотов ----------

def buyout_request_inline_keyboard(request_id):
    kb = [
        [InlineKeyboardButton(text="💰 Предложить цену", callback_data=f"offer_{request_id}")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_req_{request_id}")],
        [InlineKeyboardButton(text="📈 История ставок", callback_data=f"history_{request_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def my_request_inline_keyboard(request_id):
    kb = [
        [InlineKeyboardButton(text="📊 Посмотреть предложения", callback_data=f"view_offers_{request_id}")],
        [InlineKeyboardButton(text="📈 История ставок", callback_data=f"history_{request_id}")],
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"cancel_req_{request_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def offers_inline_keyboard(offers, request_id):
    builder = InlineKeyboardBuilder()
    for offer_id, reseller_id, price, created_at in offers:
        builder.button(text=f"{price} ₽ - выбрать", callback_data=f"choose_offer_{offer_id}_{request_id}")
    builder.adjust(1)
    return builder.as_markup()

def resale_lot_inline_keyboard(lot_id, price, is_favorite=False, is_owner=False):
    fav_text = "✅ В избранном" if is_favorite else "⭐ В избранное"
    kb = []
    if not is_owner:
        kb.append([InlineKeyboardButton(text=f"🛒 Купить за {price} ₽", callback_data=f"buy_{lot_id}")])
        kb.append([InlineKeyboardButton(text="💬 Предложить цену", callback_data=f"offer_price_{lot_id}")])
        kb.append([InlineKeyboardButton(text=fav_text, callback_data=f"fav_{lot_id}")])
        kb.append([InlineKeyboardButton(text="⚠️ Пожаловаться", callback_data=f"complaint_{lot_id}")])
    else:
        kb.append([InlineKeyboardButton(text="📊 Статистика", callback_data=f"lot_stats_{lot_id}")])
    kb.append([InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_lot_{lot_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def payment_keyboard():
    kb = [
        [InlineKeyboardButton(text="💳 500 ₽", callback_data="pay_500")],
        [InlineKeyboardButton(text="💳 1000 ₽", callback_data="pay_1000")],
        [InlineKeyboardButton(text="💳 2000 ₽", callback_data="pay_2000")],
        [InlineKeyboardButton(text="💳 5000 ₽", callback_data="pay_5000")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_wallet")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def subscriptions_multiselect_keyboard(current_subs):
    from database import get_categories
    categories = get_categories()
    builder = InlineKeyboardBuilder()
    for cat_id, cat_name in categories:
        sub = next((s for s in current_subs if s[0] == cat_id), None)
        new_text = "🆕" if (sub and sub[1]) else "⬜"
        price_text = "💰" if (sub and sub[2]) else "⬜"
        end_text = "⏰" if (sub and sub[3]) else "⬜"
        builder.button(text=f"{cat_name} {new_text}{price_text}{end_text}", callback_data=f"sub_settings_{cat_id}")
    all_subs = [s for s in current_subs if s[0] is None]
    all_new = "🆕" if all_subs and all_subs[0][1] else "⬜"
    all_price = "💰" if all_subs and all_subs[0][2] else "⬜"
    all_end = "⏰" if all_subs and all_subs[0][3] else "⬜"
    builder.button(text=f"Все категории {all_new}{all_price}{all_end}", callback_data="sub_settings_all")
    builder.button(text="💾 Сохранить", callback_data="sub_save")
    builder.adjust(2)
    return builder.as_markup()

def subscription_settings_keyboard(cat_id, current):
    new_status = "✅" if current[1] else "⬜"
    price_status = "✅" if current[2] else "⬜"
    end_status = "✅" if current[3] else "⬜"
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{new_status} Новые лоты", callback_data=f"sub_toggle_new_{cat_id}")
    builder.button(text=f"{price_status} Снижение цены", callback_data=f"sub_toggle_price_{cat_id}")
    builder.button(text=f"{end_status} Окончание аукциона", callback_data=f"sub_toggle_end_{cat_id}")
    builder.button(text="🔙 Назад", callback_data="sub_back")
    builder.adjust(1)
    return builder.as_markup()