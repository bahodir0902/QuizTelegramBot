"""Static constants."""

ASK_QUESTION_TEXT = 0
ASK_OPTIONS = 1
ASK_CORRECT_INDEX = 2
ASK_NUM_QUESTIONS = 3
ASK_TIMER_SECONDS = 4
ASK_EDIT_QUESTION_TEXT = 5
ASK_EDIT_OPTIONS = 6
ASK_EDIT_CORRECT_INDEX = 7
ASK_EDIT_ABOUT_TEXT = 8
ASK_ONBOARD_FULL_NAME = 10
ASK_ONBOARD_AGE = 11
ASK_ONBOARD_REGION = 12

SUPPORTED_LANGUAGES = ("en", "ru", "uz")

CB_ADMIN_ADD = "admin:add"
CB_ADMIN_SETTINGS = "admin:settings"
CB_ADMIN_STATS = "admin:stats"
CB_ADMIN_EXPORT = "admin:export"
CB_ADMIN_BACK = "admin:back"
CB_ADMIN_QUESTIONS = "admin:questions"
CB_ADMIN_ABOUT = "admin:about"
CB_SET_LIMIT = "settings:limit"
CB_TOGGLE_Q_SHUFFLE = "settings:q_shuffle"
CB_TOGGLE_OPT_SHUFFLE = "settings:opt_shuffle"
CB_SET_TIMER = "settings:timer"
CB_EDIT_ABOUT_PREFIX = "about:edit:"

CB_QUESTION_VIEW_PREFIX = "question:view:"
CB_QUESTION_EDIT_TEXT_PREFIX = "question:edit_text:"
CB_QUESTION_EDIT_OPTIONS_PREFIX = "question:edit_options:"
CB_QUESTION_EDIT_CORRECT_PREFIX = "question:edit_correct:"
CB_QUESTION_DELETE_CONFIRM_PREFIX = "question:delete_confirm:"
CB_QUESTION_DELETE_PREFIX = "question:delete:"
CB_QUESTION_OPTIONS_PREFIX = "question:options:"
CB_QUESTION_DELETE_OPTION_PREFIX = "question:delete_option:"
