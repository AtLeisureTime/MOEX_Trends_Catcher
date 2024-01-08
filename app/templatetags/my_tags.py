from django import template

register = template.Library()


@register.filter
def index(lst, i):
    try:
        return lst[i]
    except Exception:
        return None


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    # collect and urlencode all params of GET request
    query = context['request'].GET.copy()
    for k, v in kwargs.items():
        query[k] = v
    return query.urlencode()
