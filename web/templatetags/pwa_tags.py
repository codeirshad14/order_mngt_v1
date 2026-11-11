"""Template tags for the app-install tags every page carries in its <head>.

A tag rather than a context processor, so settings.py does not need to change.
"""

from django import template

from web import services

register = template.Library()


# "https://order.initiatorsolutions.com" — for canonical links.
@register.simple_tag
def site_url():
    return services.SITE_URL


# The name under the app icon on an iPhone's home screen.
@register.simple_tag
def pwa_short_name():
    return services.short_name(services.get_company())
