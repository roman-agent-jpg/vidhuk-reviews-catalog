"""
SEO Catalog Taxonomy Module.

Categorizes business organizations into 12 primary commercial clusters (+ fallback 'other')
and maps each cluster to appropriate Schema.org types for Google Rich Snippets compliance.
"""

from typing import Any, Dict, List, Optional, Tuple
import re

# Definitions of 12 commercial clusters + fallback 'other'
CLUSTERS: Dict[str, Dict[str, Any]] = {
    "ecommerce_shops": {
        "id": "ecommerce_shops",
        "label_ru": "Интернет-магазины и торговля",
        "label_ua": "Інтернет-магазини та торгівля",
        "schema_type": "Store",
        "description_ru": "Каталог интернет-магазинов, розничной и оптовой торговли, маркетплейсов и служб доставки.",
        "description_ua": "Каталог інтернет-магазинів, роздрібної та оптової торгівлі, маркетплейсів та служб доставки.",
        "keywords_ru": ["интернет-магазин", "магазин", "маркетплейс", "купить онлайн", "доставка товаров"],
        "keywords_ua": ["інтернет-магазин", "магазин", "маркетплейс", "купити онлайн", "доставка товарів"],
    },
    "auto_transport": {
        "id": "auto_transport",
        "label_ru": "Авто и транспорт",
        "label_ua": "Авто та транспорт",
        "schema_type": "AutomotiveBusiness",
        "description_ru": "Автосалоны, СТО, шиномонтаж, запчасти, грузовые и пассажирские перевозки, логистика и такси.",
        "description_ua": "Автосалони, СТО, шиномонтаж, запчастини, вантажні та пасажирські перевезення, логістика та таксі.",
        "keywords_ru": ["автосервис", "сто", "автозапчасти", "перевозки", "логистика", "прокат авто"],
        "keywords_ua": ["автосервіс", "сто", "автозапчастини", "перевезення", "логістика", "прокат авто"],
    },
    "finance_crypto": {
        "id": "finance_crypto",
        "label_ru": "Финансы, банки и крипта",
        "label_ua": "Фінанси, банки та крипта",
        "schema_type": "FinancialService",
        "description_ru": "Банки, микрозаймы (МФО), кредитование, страхование, лизинг, криптовалютные биржи и обменники.",
        "description_ua": "Банки, мікропозики (МФО), кредитування, страхування, лізинг, криптовалютні біржі та обмінники.",
        "keywords_ru": ["банк", "кредит", "займ онлайн", "криптовалюта", "обменник биткоин", "страховая компания"],
        "keywords_ua": ["банк", "кредит", "позика онлайн", "криптовалюта", "обмінник біткоїн", "страхова компанія"],
    },
    "medicine_health": {
        "id": "medicine_health",
        "label_ru": "Медицина и здоровье",
        "label_ua": "Медицина та здоров'я",
        "schema_type": "MedicalBusiness",
        "description_ru": "Медицинские центры, клиники, стоматологии, лаборатории, диагностика, аптеки и ветеринария.",
        "description_ua": "Медичні центри, клініки, стоматології, лабораторії, діагностика, аптеки та ветеринарія.",
        "keywords_ru": ["медицинский центр", "клиника", "стоматология", "аптека", "врачи", "лаборатория"],
        "keywords_ua": ["медичний центр", "клініка", "стоматологія", "аптека", "лікарі", "лабораторія"],
    },
    "it_web": {
        "id": "it_web",
        "label_ru": "IT, веб-сайты и софт",
        "label_ua": "IT, веб-сайти та софт",
        "schema_type": "ProfessionalService",
        "description_ru": "IT-компании, веб-студии, разработка программного обеспечения, хостинг, digital-агентства и полиграфия.",
        "description_ua": "IT-компанії, веб-студії, розробка програмного забезпечення, хостинг, digital-агентства та поліграфія.",
        "keywords_ru": ["it-компания", "разработка сайтов", "софт", "хостинг", "веб-студия", "маркетинг"],
        "keywords_ua": ["it-компанія", "розробка сайтів", "софт", "хостинг", "веб-студія", "маркетинг"],
    },
    "beauty_services": {
        "id": "beauty_services",
        "label_ru": "Салоны красоты и СПА",
        "label_ua": "Салони краси та СПА",
        "schema_type": "BeautySalon",
        "description_ru": "Салоны красоты, парикмахерские, барбершопы, маникюр, СПА-центры, косметология и тату-салоны.",
        "description_ua": "Салони краси, перукарні, барбершопи, манікюр, СПА-центри, косметологія та тату-салони.",
        "keywords_ru": ["салон красоты", "барбершоп", "косметология", "массаж", "спа", "маникюр"],
        "keywords_ua": ["салон краси", "барбершоп", "косметологія", "масаж", "спа", "манікюр"],
    },
    "education": {
        "id": "education",
        "label_ru": "Курсы и образование",
        "label_ua": "Курси та освіта",
        "schema_type": "EducationalOrganization",
        "description_ru": "Онлайн-школы, языковые курсы, автошколы, университеты, репетиторы, тренинги и вебинары.",
        "description_ua": "Онлайн-школи, мовні курси, автошколи, університети, репетитори, тренінги та вебінари.",
        "keywords_ru": ["онлайн курсы", "школа", "обучение", "репетитор", "автошкола", "академия"],
        "keywords_ua": ["онлайн курси", "школа", "навчання", "репетитор", "автошкола", "академія"],
    },
    "construction_repair": {
        "id": "construction_repair",
        "label_ru": "Строительство и ремонт",
        "label_ua": "Будівництво та ремонт",
        "schema_type": "HomeAndConstructionBusiness",
        "description_ru": "Строительные компании, ремонт квартир, стройматериалы, сантехника, окна, двери, монтаж и коммуникации.",
        "description_ua": "Будівельні компанії, ремонт квартир, будматеріали, сантехніка, вікна, двері, монтаж та комунікації.",
        "keywords_ru": ["строительство", "ремонт квартир", "стройматериалы", "окна", "сантехника", "электромонтаж"],
        "keywords_ua": ["будівництво", "ремонт квартир", "будматеріали", "вікна", "сантехніка", "електромонтаж"],
    },
    "furniture_home": {
        "id": "furniture_home",
        "label_ru": "Мебель и товары для дома",
        "label_ua": "Меблі та товари для дому",
        "schema_type": "FurnitureStore",
        "description_ru": "Производство и продажа мебели, кухни, матрасы, интерьер, текстиль, посуда, товары для сада и дома.",
        "description_ua": "Виробництво та продаж меблів, кухні, матраци, інтер'єр, текстиль, посуд, товари для саду та дому.",
        "keywords_ru": ["мебель", "диваны", "кухни на заказ", "матрасы", "товары для дома", "интерьер"],
        "keywords_ua": ["меблі", "дивани", "кухні на замовлення", "матраци", "товари для дому", "інтер'єр"],
    },
    "jobs_employment": {
        "id": "jobs_employment",
        "label_ru": "Работа и трудоустройство",
        "label_ua": "Робота та працевлаштування",
        "schema_type": "EmploymentAgency",
        "description_ru": "Кадровые агентства, работа за границей, трудоустройство, рекрутинг, визовая поддержка и вакансии.",
        "description_ua": "Кадрові агентства, робота за кордоном, працевлаштування, рекрутинг, візова підтримка та вакансії.",
        "keywords_ru": ["работа за границей", "трудоустройство", "вакансии", "кадровое агентство", "рекрутинг"],
        "keywords_ua": ["робота за кордоном", "працевлаштування", "вакансії", "кадрове агентство", "рекрутинг"],
    },
    "tourism_leisure": {
        "id": "tourism_leisure",
        "label_ru": "Туризм, отдых и развлечения",
        "label_ua": "Туризм, відпочинок та розваги",
        "schema_type": "LodgingBusiness",
        "description_ru": "Отели, базы отдыха, глэмпинги, рестораны, кафе, туроператоры, путешествия, спортклубы и казино.",
        "description_ua": "Готелі, бази відпочинку, глемпінги, ресторани, кафе, туроператори, подорожі, спортклуби та казино.",
        "keywords_ru": ["отель", "база отдыха", "туроператор", "ресторан", "кафе", "развлечения"],
        "keywords_ua": ["готель", "база відпочинку", "туроператор", "ресторан", "кафе", "розваги"],
    },
    "legal_consulting": {
        "id": "legal_consulting",
        "label_ru": "Юридические услуги и консалтинг",
        "label_ua": "Юридичні послуги та консалтинг",
        "schema_type": "LegalService",
        "description_ru": "Адвокаты, юристы, нотариусы, бухгалтерские услуги, аудит, консалтинг и регистрация бизнеса.",
        "description_ua": "Адвокати, юристи, нотаріуси, бухгалтерські послуги, аудит, консалтинг та реєстрація бізнесу.",
        "keywords_ru": ["юрист", "адвокат", "юридические услуги", "бухгалтер", "нотариус", "консалтинг"],
        "keywords_ua": ["юрист", "адвокат", "юридичні послуги", "бухгалтер", "нотаріус", "консалтинг"],
    },
    "other": {
        "id": "other",
        "label_ru": "Другие компании и услуги",
        "label_ua": "Інші компанії та послуги",
        "schema_type": "LocalBusiness",
        "description_ru": "Широкий спектр компаний, услуг, сервисов и потребительских организаций.",
        "description_ua": "Широкий спектр компаній, послуг, сервісів та споживчих організацій.",
        "keywords_ru": ["услуги", "компании", "отзывы", "рейтинг"],
        "keywords_ua": ["послуги", "компанії", "відгуки", "рейтинг"],
    },
}

# Explicit Schema.org org_type mapping
ORG_TYPE_MAP: Dict[str, Tuple[str, str]] = {
    # Finance
    "BankOrCreditUnion": ("finance_crypto", "BankOrCreditUnion"),
    "InsuranceAgency": ("finance_crypto", "InsuranceAgency"),
    "PawnShop": ("finance_crypto", "PawnShop"),
    # Auto & Transport
    "AutoRepair": ("auto_transport", "AutoRepair"),
    "AutoPartsStore": ("auto_transport", "AutoPartsStore"),
    "AutoDealer": ("auto_transport", "AutoDealer"),
    "AutoRental": ("auto_transport", "AutoRental"),
    "AutoWash": ("auto_transport", "AutoWash"),
    "Airline": ("auto_transport", "Airline"),
    "GasStation": ("auto_transport", "GasStation"),
    "MotorcycleDealer": ("auto_transport", "MotorcycleDealer"),
    # Medicine
    "MedicalClinic": ("medicine_health", "MedicalClinic"),
    "Dentist": ("medicine_health", "Dentist"),
    "Pharmacy": ("medicine_health", "Pharmacy"),
    "Physician": ("medicine_health", "Physician"),
    "Hospital": ("medicine_health", "Hospital"),
    "MedicalOrganization": ("medicine_health", "MedicalBusiness"),
    "VeterinaryCare": ("medicine_health", "VeterinaryCare"),
    # Beauty & Wellness
    "BeautySalon": ("beauty_services", "BeautySalon"),
    "DaySpa": ("beauty_services", "DaySpa"),
    # Tourism, Leisure & Food
    "Hotel": ("tourism_leisure", "Hotel"),
    "Restaurant": ("tourism_leisure", "Restaurant"),
    "FastFoodRestaurant": ("tourism_leisure", "FastFoodRestaurant"),
    "BarOrPub": ("tourism_leisure", "BarOrPub"),
    "TravelAgency": ("tourism_leisure", "TravelAgency"),
    "SportsClub": ("tourism_leisure", "SportsClub"),
    "HealthClub": ("tourism_leisure", "HealthClub"),
    "Casino": ("tourism_leisure", "Casino"),
    "Movie": ("tourism_leisure", "Movie"),
    "Event": ("tourism_leisure", "Event"),
    # Construction & Furniture
    "HardwareStore": ("construction_repair", "HardwareStore"),
    "FurnitureStore": ("furniture_home", "FurnitureStore"),
    "HomeGoodsStore": ("furniture_home", "HomeGoodsStore"),
    "GardenStore": ("furniture_home", "GardenStore"),
    # Employment
    "EmploymentAgency": ("jobs_employment", "EmploymentAgency"),
    # Specific Stores
    "ElectronicsStore": ("ecommerce_shops", "ElectronicsStore"),
    "ClothingStore": ("ecommerce_shops", "ClothingStore"),
    "ShoeStore": ("ecommerce_shops", "ShoeStore"),
    "GroceryStore": ("ecommerce_shops", "GroceryStore"),
    "Florist": ("ecommerce_shops", "Florist"),
    "SportingGoodsStore": ("ecommerce_shops", "SportingGoodsStore"),
    "JewelryStore": ("ecommerce_shops", "JewelryStore"),
    "PetStore": ("ecommerce_shops", "PetStore"),
    "ToyStore": ("ecommerce_shops", "ToyStore"),
    "BookStore": ("ecommerce_shops", "BookStore"),
    "ComputerStore": ("ecommerce_shops", "ComputerStore"),
    "MobilePhoneStore": ("ecommerce_shops", "MobilePhoneStore"),
    "DepartmentStore": ("ecommerce_shops", "DepartmentStore"),
    "HobbyShop": ("ecommerce_shops", "HobbyShop"),
    "DryCleaningOrLaundry": ("other", "LocalBusiness"),
}

# Compiled regex keyword patterns for bilingual analysis
COMPILED_PATTERNS: Dict[str, re.Pattern] = {
    "finance_crypto": re.compile(
        r"\b(банк|банкі|банківськ|кредит|займ|заем|заём|мікропозик|микрозайм|мфо|гроші|ломбард|крипт|crypto|битко|бітко|bitcoin|btc|usdt|обменник|обмінник|форекс|forex|трейдинг|инвестиц|інвестиц|брокер|страхован|страхуван|страховая|страхова|платежн|платіжн|лизинг|лізинг|депозит|рассрочк|розстрочк)\w*",
        re.IGNORECASE,
    ),
    "auto_transport": re.compile(
        r"\b(авто|машин|запчаст|сто|шиномонтаж|автосервис|автосервіс|автосалон|автопрокат|прокат авто|оренда авто|аренда авто|автомийк|автомойк|перевозк|перевезен|грузоперевоз|вантажні|логистик|логістик|автобус|такси|таксі|эвакуатор|евакуатор|шины|шини|диски|авторазборк|авторозбірк|заправк|азс|самокат|електросамокат|пассажирск|пасажирськ)\w*",
        re.IGNORECASE,
    ),
    "medicine_health": re.compile(
        r"\b(клиник|клінік|медицин|медичн|врач|лікар|стоматолог|зубн|аптек|лекарств|ліки|фармац|больниц|лікарн|поликлиник|поліклінік|диагностик|діагностик|анализ|аналіз|узи|узд|мрт|лаборатор|терапевт|хирург|хірург|офтальмолог|гинеколог|гінеколог|ветеринар|ветклінік|ветклиник|реабилитац|реабілітац|нарколог|препарат|таблетк|краплі|снотворн|вітамін|бад)\w*",
        re.IGNORECASE,
    ),
    "education": re.compile(
        r"\b(курс|школ|обучен|навчан|онлайн-школ|академи|академі|университет|університет|колледж|коледж|репетитор|английск|англійськ|автошкол|автошкіл|тренинг|тренінг|вебинар|вебінар|образован|освіт|преподавател|викладач|зно|нмт|студент|урок|диплом|курсовые|бизнес-образование|бізнес-освіта)\w*",
        re.IGNORECASE,
    ),
    "beauty_services": re.compile(
        r"\b(салон красот|салон краси|парикмахер|перукарн|барбер|маникюр|манікюр|педикюр|ногти|нігті|косметолог|спа|spa|массаж|масаж|эпиляц|епіляц|депиляц|депіляц|брови|ресниц|вії|визаж|візаж|тату|пирсинг|пірсинг|соляри|косметик|шугаринг)\w*",
        re.IGNORECASE,
    ),
    "jobs_employment": re.compile(
        r"\b(робота за кордоном|работа за границей|трудоустрой|працевлаштуван|поиск работы|пошук роботи|ваканси|вакансі|рекрутинг|подбор персонала|підбір персоналу|визовая поддержка|візова підтримка|работа в польше|робота в польщі|работодател|роботодав|кадров|собеседован|співбесід|зарплат)\w*",
        re.IGNORECASE,
    ),
    "legal_consulting": re.compile(
        r"\b(юридическ|юридичн|юрист|адвокат|нотариус|нотаріус|консультация юриста|консультація юриста|бухгалтер|аудит|налоговый|податковий|регистрация бизнеса|реєстрація бізнесу|судебные споры|судові спори|банкротств|банкрутств|патент|консалтинг|юриспруденц)\w*",
        re.IGNORECASE,
    ),
    "construction_repair": re.compile(
        r"\b(строительств|будівництв|стройматериал|будматеріал|ремонт квартир|отделк|оздоблен|монтаж|кровл|покрівл|фасад|окна|вікна|двери|двері|ворота|роллет|ролет|сантехник|электрик|електрик|вентиляц|отоплен|опален|кондиционер|кондиціонер|плитка|ламинат|ламінат|натяжные потолки|натяжні стелі|металлопрокат|металопрокат|бетон|кирпич|цегл|архитектур|бурение|свердління|утеплен)\w*",
        re.IGNORECASE,
    ),
    "furniture_home": re.compile(
        r"\b(мебел|мебл|диван|кроват|ліжк|кухн|шкаф|шаф|матрас|матрац|интерьер|інтер\'єр|текстил|посуд|декор|ковр|килим|люстр|светильник|світильник|товары для дома|товари для дому|постельное белье|постільна білизна|сад и огород|сад та город|семен|насінн|саженц|саджанц|теплиц|жалюзи|жалюзі)\w*",
        re.IGNORECASE,
    ),
    "it_web": re.compile(
        r"\b(it-компани|it-компані|веб-студи|веб-студі|разработка сайтов|розробка сайтів|создание сайтов|створення сайтів|программирован|програмуван|софт|программное обеспечение|програмне забезпечення|хостинг|домен|crm|мобильные приложения|мобільні додатки|saas|digital-агент|digital-агенц|маркетинг|таргетинг|smm|контекстная реклама|контекстна реклама|провайдер|интернет-провайдер|інтернет-провайдер|полиграфи|поліграфі|типографи|типографі|печать|друк)\w*",
        re.IGNORECASE,
    ),
    "tourism_leisure": re.compile(
        r"\b(отел|готел|гостиниц|хостел|база отдыха|база відпочинку|санатори|санаторі|пансионат|пансіонат|туризм|тур|путевк|путівк|туроператор|турагент|турагенц|отдых|відпочинок|экскурси|екскурсі|ресторан|кафе|бар|паб|пиццери|піцері|суши|суші|доставка еды|доставка їжі|боулинг|боулінг|бильярд|більярд|кинотеатр|кінотеатр|фитнес|фітнес|спортзал|спортклуб|бассейн|басейн|казино|casino|кемпинг|кемпінг|глемпинг|глемпінг|курорт)\w*",
        re.IGNORECASE,
    ),
    "ecommerce_shops": re.compile(
        r"\b(интернет-магазин|інтернет-магазин|магазин|маркет|супермаркет|гипермаркет|гіпермаркет|бутик|бутік|торговый дом|каталог товаров|онлайн-шоп|шопинг|шопінг|купить|купити|дропшип|заказ товаров|замовлення товарів|аксессуар|аксесуар|одежд|одяг|обувь|взуття|косметика|парфюм|парфум|кондитерск|солодощ|упаковк|пакуванн|подар|подарунк|ювелир|ювелір|доставка по украине|доставка по україні|ассортимент|асортимент)\w*",
        re.IGNORECASE,
    ),
}

# Priority order for keyword testing: high-specificity domains first
SEARCH_PRIORITY: List[str] = [
    "finance_crypto",
    "medicine_health",
    "education",
    "jobs_employment",
    "legal_consulting",
    "beauty_services",
    "construction_repair",
    "furniture_home",
    "auto_transport",
    "tourism_leisure",
    "it_web",
    "ecommerce_shops",
]


def classify_company(
    name: str,
    org_type: Optional[str] = None,
    description: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Classifies a company into one of the 12 semantic clusters (+ fallback 'other')
    and returns (cluster_id, schema_org_type).

    Parameters:
        name: Company title or brand name.
        org_type: Donor Schema.org type if available (e.g. 'Store', 'MedicalClinic').
        description: Organization description or category tag string.

    Returns:
        Tuple[str, str]: (cluster_id, schema_org_type)
    """
    clean_name = (name or "").strip()
    clean_type = (org_type or "").strip()
    clean_desc = (description or "").strip()

    # 1. Tier 1: Check specific org_type map (non-generic types)
    if clean_type in ORG_TYPE_MAP:
        cluster_id, schema_type = ORG_TYPE_MAP[clean_type]
        # If the type is highly specific, we can return immediately
        if clean_type not in {"Store", "LocalBusiness", "Organization", "Product"}:
            return cluster_id, schema_type

    # 2. Tier 2: Check category tags in description (Vidhuk.ua structured tags)
    # E.g. "Бизнес-образование", "Пассажирские перевозки", "Автозапчасти", "Стоматология"
    combined_text = f"{clean_name} {clean_desc}"
    for cid in SEARCH_PRIORITY:
        pattern = COMPILED_PATTERNS.get(cid)
        if pattern and pattern.search(combined_text):
            # If donor org_type was a specific valid subtype, preserve it; otherwise use cluster's schema_type
            if clean_type in ORG_TYPE_MAP and ORG_TYPE_MAP[clean_type][0] == cid:
                schema_type = ORG_TYPE_MAP[clean_type][1]
            else:
                schema_type = CLUSTERS[cid]["schema_type"]
            return cid, schema_type

    # 3. Tier 3: If org_type was 'Store' or maps to Store
    if clean_type == "Store" or clean_type == "ClothingStore" or clean_type == "ElectronicsStore":
        return "ecommerce_shops", clean_type if clean_type != "Store" else "Store"

    # 4. Tier 4: Fallback to 'other' / 'LocalBusiness'
    return "other", "LocalBusiness"


def get_cluster_info(cluster_id: str) -> Dict[str, Any]:
    """
    Returns full metadata for a given cluster.
    Falls back to 'other' if unknown cluster_id is provided.
    """
    return CLUSTERS.get(cluster_id, CLUSTERS["other"])


def list_all_clusters() -> List[Dict[str, Any]]:
    """
    Returns all 12 commercial clusters + fallback 'other' in canonical order.
    """
    ordered_ids = SEARCH_PRIORITY + ["other"]
    return [CLUSTERS[cid] for cid in ordered_ids if cid in CLUSTERS]
