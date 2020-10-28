# coding=utf-8
from base.wrapper import transaction, doc, DB, uidoc
from base.exeption import ScriptError
import logging
import System


def main():
    FILTER_NAME = IN[0]
    COLOR = IN[1]
    VISIBLE = IN[2]
    HALFTONE = IN[3]
    views = get_selected_views()
    for view in views:
        add_filter_by_name_to_view(view, FILTER_NAME, COLOR, VISIBLE, HALFTONE)


def add_filter_by_name_to_view(view, filter_name, color='##808080', visible=True, halftone=False):
    view_filter = get_view_filter(filter_name)

    filter_props = {
        "visible": visible,
        "halftone": halftone,
        "color": hex_string_to_color(color),
        "pattern_id": get_fill_pattern_id()}

    add_filter(view, view_filter, **filter_props)
    logging.debug("Filter '{}' #{} added to view '{}' #{}".format(
        view_filter.Name, view_filter.Id, view.Name, view.Id))


def get_selected_views():
    return filter_views_from(get_selected_ids())


def get_selected_ids():
    """Вернуть id выбранных в Ревите элементов"""
    selected_ids = uidoc.Selection.GetElementIds()
    if not selected_ids:
        raise ScriptError('No view is selected. Please select one or several views')
    return selected_ids


def filter_views_from(ids):
    """Выбрать виды из списка id"""
    views = DB.FilteredElementCollector(doc, ids).OfClass(DB.View)
    if not views.GetElementCount():
        raise ScriptError('Choose at least one species')
    return views


def get_view_filter(filter_name):
    """Получение фильтра с заданным именем"""
    par_filters = DB.FilteredElementCollector(doc).OfClass(DB.ParameterFilterElement)
    for p in par_filters:
        if p.Name == filter_name:
            return p

    raise ScriptError('The project does not have a filter named {}'.format(filter_name))


@transaction
def add_filter(view, view_filter, **kwargs):
    """Переопределить графику и добавить фильтр на вид"""
    ogs = DB.OverrideGraphicSettings()
    ogs.SetHalftone(kwargs.get('halftone', False))

    pattern_id = kwargs.get('pattern_id', None)
    if pattern_id:
        ogs.SetCutForegroundPatternId(pattern_id)
        ogs.SetSurfaceForegroundPatternId(pattern_id)

    color = kwargs.get('color', None)
    if color:
        ogs.SetCutForegroundPatternColor(color)
        ogs.SetSurfaceForegroundPatternColor(color)

    view.SetFilterOverrides(view_filter.Id, ogs)
    view.SetFilterVisibility(view_filter.Id, kwargs.get("visible", True))


def hex_string_to_color(hex_str):
    """Получения цвета из HEX"""
    try:
        hex_str = hex_str.lstrip('##')
        r, g, b = (int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        return DB.Color(System.Byte(r), System.Byte(g), System.Byte(b))

    except Exception as err:
        raise ScriptError('Color Convert Error:' + err.args[0])


def get_fill_pattern_id():
    """Получение id первой сплошной заливки"""
    patterns = DB.FilteredElementCollector(doc).OfClass(DB.FillPatternElement).WhereElementIsNotElementType()
    for pat in patterns:
        if pat.GetFillPattern().IsSolidFill:
            return pat.Id

    raise ScriptError('There is no solid pattern in the project!')


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.DEBUG,
        format='[%(asctime)s] %(levelname).1s <adder_filter>: %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S')

    try:
        main()

    except ScriptError as e:
        logging.error(e)
    except Exception:
        logging.exception('Critical error')
