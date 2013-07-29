from django.template.loader import BaseLoader


class MockLoader(BaseLoader):

    is_usable = True

    def load_template_source(self, template_name, template_dirs=None):
        return '<div></div>', 'template.html'
