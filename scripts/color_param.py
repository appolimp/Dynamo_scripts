# coding=utf-8
from base.wrapper import transaction, doc, DB
from adder_filter import add_filter_by_name_to_view, get_selected_views
from base.exeption import ScriptError
from base.color import ColorCoroutine
import logging

from System.Collections.Generic import List


def main():
    PARAM_NAME = IN[0]
    VISIBLE = IN[1]
    HALFTONE = IN[2]
    views = get_selected_views()
    val_col = get_val_col_by_param(PARAM_NAME)
    for val, col in val_col:
        color_elem_on_views_by_param(views, PARAM_NAME, value=val, color=col, visible=VISIBLE, halftone=HALFTONE)
    return [val for val, col in val_col]


def get_val_col_by_param(param_name):
    val = get_val_by_param(param_name)
    colors = ColorCoroutine().create_color()
    col = [next(colors) for _ in range(len(val))]
    logging.info("Get all values of parameter '{}'. Count = {}".format(param_name, len(val)))
    return zip(val, col)


def get_val_by_param(param_name):
    values = set()

    for cat in get_cat_id_list_by_param_name(param_name):
        elem_list = DB.FilteredElementCollector(doc).OfCategoryId(cat).WhereElementIsNotElementType().ToElements()
        for elem in elem_list:
            values.add(get_val_of_param_elem(elem, param_name))

    for i in (None, ''):
        values.remove(i) if i in values else None

    return list(sorted(values))


def get_val_of_param_elem(elem, param_name):
    elem_par = elem.GetParameters(param_name)
    if not elem_par:
        raise ScriptError("Param '{}' not found in elem #{}".format(param_name, elem.Id))
    elem_par = elem_par[0]
    if elem_par.StorageType == DB.StorageType.String:
        return elem_par.AsString()
    if elem_par.StorageType == DB.StorageType.Integer:
        return elem_par.AsInteger()
    if elem_par.StorageType == DB.StorageType.Double:
        return elem_par.AsDouble()

    raise ScriptError("Param '{}' have unknown type".format(param_name))


def color_elem_on_views_by_param(views, param_name, value, color, visible, halftone):
    filter_name = param_name + '_' + value
    for ch in (';',):
        if ch in filter_name:
            filter_name = filter_name.replace(ch, '__')
    my_filter = get_or_create_filter(filter_name, param_name, value)
    for view in views:
        add_filter_by_name_to_view(view, my_filter.Name, color, visible, halftone)
    logging.info("Color elements, where '{}' == {}".format(param_name, value))


def get_or_create_filter(filter_name, param_name, value):
    """return filter with actual cat_id and equal rule"""
    cat_id = get_cat_id_list_by_param_name(param_name)
    try:
        my_filter = find_filter(filter_name)
        set_cat(my_filter, cat_id)
    except KeyError:
        my_filter = create_filter(filter_name, cat_id)

    rule = create_equal_rule(param_name, value)
    set_rule(my_filter, rule)

    return my_filter


def find_filter(name):
    data = DB.FilteredElementCollector(doc).OfClass(DB.ParameterFilterElement).WhereElementIsNotElementType()
    for el in data:
        if el.Name == name:
            logging.debug("Find filter '{}' #{}".format(el.Name, el.Id))
            return el

    logging.debug("Project doesn't have a filter '{}'".format(name))
    raise KeyError('Filter not Found')


@transaction
def set_cat(view_filter, cat_id):
    view_filter.SetCategories(cat_id)
    logging.debug("Set new categories to '{}' #{}".format(view_filter.Name, view_filter.Id))


@transaction
def create_filter(name_filter, cat_id):
    new_filter = DB.ParameterFilterElement.Create(doc, name_filter, cat_id)
    logging.debug("Create new filter '{}' #{}".format(new_filter.Name, new_filter.Id))
    return new_filter


def get_cat_id_list_by_cat_name(cat_names):
    """cat_names = ['OST_Walls', 'OST_Floors']"""
    cats = []
    for cat_name in cat_names:
        cat = DB.Category.GetCategory(doc, getattr(DB.BuiltInCategory, cat_name))
        cats.append(cat.Id)
    typed_cat_list = List[DB.ElementId](cats)
    logging.debug('Get cat_id by cat_names: {} pieces'.format(len(typed_cat_list)))

    return typed_cat_list


def get_cat_id_list_by_param_name(param_names):
    param = get_param_by(param_names)

    binding_map = doc.ParameterBindings
    binding = binding_map.Item[param.GetDefinition()]
    category_set = binding.Categories.GetEnumerator()

    cat_ids = [cat.Id for cat in category_set]
    cat_ids_list = List[DB.ElementId](cat_ids)

    # Clear cat, which can not be applied to filter
    cat_ids_valid = DB.ParameterFilterUtilities.RemoveUnfilterableCategories(cat_ids_list)

    logging.debug("Get cat_id by param_name: {} pieces".format(len(cat_ids_valid)))
    return cat_ids_valid


def get_param_by(param_name):
    """Return parameter"""
    param_elems = DB.FilteredElementCollector(doc).OfClass(DB.ParameterElement).ToElements()
    for param in param_elems:
        if param.Name == param_name:
            logging.debug("Find parameter '{}' #{}".format(param.Name, param.Id))
            return param

    """
    Иногда выдавал ошибку: The managed object is not valid.
    iterator = doc.ParameterBindings.ForwardIterator()
    iterator.Reset()

    while iterator.MoveNext():
        if iterator.Key.Name == param_name:
            param = iterator.Key
            logging.debug("Find parameter '{}' #{}".format(param.Name, param.Id))
            return param
    """
    raise ScriptError("The project does not have a parameter named '{}'".format(param_name))


def create_equal_rule(param_name, val):
    param = DB.ParameterValueProvider(get_param_by(param_name).Id)
    rule = DB.ElementParameterFilter(DB.FilterStringRule(param, DB.FilterStringEquals(), val, False))
    logging.debug("Create rule: ['{}' == {}]".format(param_name, val))
    """
    # add multi filters
    filters_ = List[DB.ElementFilter]()
    filters_.Add(DB.ElementParameterFilter(DB.FilterStringRule(param, DB.FilterStringEquals(), val, False)))

    fRule = DB.LogicalAndFilter(filters_)
    """
    return rule


@transaction
def set_rule(view_filter, rule):
    view_filter.SetElementFilter(rule)
    logging.debug("Set rule to filter: '{}' #{}".format(view_filter.Name, view_filter.Id))


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.INFO,
        format='[%(asctime)s] %(levelname).1s <my_script>: %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S')

    try:
        OUT = main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error')
