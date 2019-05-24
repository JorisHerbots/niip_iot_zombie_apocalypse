from microWebServer import MicroWebSrv
from volatileconfiguration import VolatileConfiguration as Config
from wifi import WIFIMODI

class InputManager:
    class InputOption:
        _hidden_text = "hidden (do not change to keep value unchanged)"

        def __init__(self, config_key, default_value, key_type=None, options=None, help_line="", hide_configured_value=False):
            """Create a user input field
            
            :param default_value: default value of the input/option field
            :type default_value: [type]
            :param key_type: defines what the input should be parsed into, defaults to None when field are options
            :param dict options: when supplied defines a set of options instead of input field, defaults to None, structure: human readable value(str) => Internal option
            """
            self.config_key = config_key
            self.default = default_value
            self.key_type = key_type
            self.options = options
            self.help_line = help_line
            self.hide_configured_value = hide_configured_value

        def set_option(self, raw_input):
            if not isinstance(raw_input, str):
                raise TypeError("Input is required to be a string. (From POST data)")
            if self.hide_configured_value and raw_input == InputManager.InputOption._hidden_text:
                return

            if self.options:
                raw_input = raw_input.replace("+", " ") # MicroWebServ quirk...
                if raw_input in self.options:
                    Config.set(self.config_key, self.options[raw_input], True, True)
                else:
                    raise TypeError("Given option is not a valid one.")
            else:
                # TODO needs expansion/better system
                # Let typecasting throw errors to an upper level (TypeError is pretty informative on itself)
                if self.key_type == str:
                    input_parsed = raw_input
                elif self.key_type == int:
                    input_parsed = int(raw_input)
                elif self.key_type == float:
                    input_parsed = float(raw_input)
                Config.set(self.config_key, input_parsed, True, True)

        def to_html(self):
            if self.options:
                html = '<h5>{} ({})</h5><select name="{}">'.format(self.config_key, self.help_line, self.config_key)
                for key, val in self.options.items():
                    default_value = Config.get(self.config_key, self.default) # None will be set to default is this value is not in the options list
                    html += '<option value="{}"{}>{}</option>'.format(key, (" selected" if val == default_value else ""), key)
                html += '</select>'
                return html
            else:
                value = InputManager.InputOption._hidden_text if self.hide_configured_value else Config.get(self.config_key, "")
                return '<h5>{} ({})</h5><input id="{}" name="{}" value="{}" placeholder="{}" /></p>'.format(self.config_key, self.help_line, self.config_key, self.config_key, value, self.default)


    inputs = {}
    categories = {} # name => priority

    @staticmethod
    def add_input(config_key, key_type, default, category, help="", hide_configured_value=False):
        InputManager.inputs[config_key] = (InputManager.InputOption(config_key=config_key, default_value=default, key_type=key_type, help_line=help, hide_configured_value=hide_configured_value), category.lower())

    @staticmethod
    def add_options(config_key, options, default, category, help=""):
        InputManager.inputs[config_key] = (InputManager.InputOption(config_key=config_key, default_value=default, options=options, help_line=help), category.lower())        

    @staticmethod
    def remove(config_key):
        InputManager.inputs.pop(config_key, None)

    @staticmethod
    def parse_input(config_key, raw_input):
        if config_key not in InputManager.inputs:
            raise KeyError("Config key [{}] not known to inputmanager".format(config_key))
        InputManager.inputs[config_key][0].set_option(raw_input)

    @staticmethod
    def set_category_priority(category, priority):
        InputManager.categories[category.lower()] = priority

    @staticmethod
    def generate_html_input_tags():
        tags = {}
        for config_key in InputManager.inputs:
            data = InputManager.inputs[config_key]
            if data[1] not in tags:
                tags[data[1]] = ""
            tags[data[1]] += data[0].to_html()
        categories = sorted(tags.keys(), key=lambda x: InputManager.categories.get(x, 99))
        html = '<form method="POST" method="/">'
        for category in categories:
            html += "<h1>{}</h1>".format(category)
            html += tags[category]
        html += '<input type="submit" value="Update Device" /></form>'
        return html

# InputManager.add_input("test1", str, "Hoi1", "global", "This is a default text")
# InputManager.add_input("test2", str, "Hoi2", "global", "This is a default text")
# InputManager.add_input("test3", int, "Hoi3", "other", "This is a default text")
# InputManager.add_options("test4", {"off":WIFIMODI.OFF, "Station":WIFIMODI.STA, "Access Point":WIFIMODI.AP, "Station - Access Point":WIFIMODI.STA_AP}, WIFIMODI.AP, "other", "help line")

@MicroWebSrv.route('/', 'GET')
def getHandler(httpClient, httpResponse):
    html = '<!DOCTYPE html><html><head><title>Device Config</title><style>h5{padding: 0px; margin: 0px;}</style><meta name="viewport" content="width=device-width"></head><body>'
    html += InputManager.generate_html_input_tags()
    html += '</body></html>'
    httpResponse.WriteResponseOk(headers=None, contentType="text/html", contentCharset="UTF-8", content=html)

@MicroWebSrv.route('/', 'POST')
def submitHandler(httpClient, httpResponse):
    # Parse input
    errors = ""
    for key, val in httpClient.ReadRequestPostedFormData().items():
        try:
            InputManager.parse_input(key, val)
        except Exception as e:
            errors += "<h5>{}</h5><p>Reason: {}</p>".format(key, str(e))
    if errors:
        errors = "<h1>Errors during saving</h1>" + errors
    
    # Save whatever got set
    Config.save_configuration_to_datastore("global")

    # Default page (with not updated values)
    html = '<!DOCTYPE html><html><head><title>Device Config</title><style>h5{padding: 0px; margin: 0px;}</style><meta name="viewport" content="width=device-width"></head><body>'
    html += errors
    html += InputManager.generate_html_input_tags()
    html += '</body></html>'
    httpResponse.WriteResponseOk(headers=None, contentType="text/html", contentCharset="UTF-8", content=html)
