# coding=utf-8
from base.wrapper import transaction, doc, DB, uidoc, UI
from base.exeption import ScriptError
from base.selection import get_selected
from base.exeption import ScriptError
import logging
import string


class SortedNumbers:
    def __init__(self):
        self.value = []

    def append(self, value):
        clean_value = self.get_clear_value(value)
        sort_value = self.get_sort_value(clean_value)

        self.value.append((sort_value, clean_value))

    def get_sorted(self):
        return list(zip(*sorted(self.value)))[1]

    @staticmethod
    def get_clear_value(value):
        return "".join(ch for ch in value if ch.isalnum() or ch in string.punctuation or ch.isspace())

    @staticmethod
    def get_sort_value(value):
        res = []
        for ch in value:
            if ch.isdigit():
                res.append(ch)
            elif res:
                break
        return int("".join(res))


def main():
    JUST_UPDATE = IN[0]

    if JUST_UPDATE:
        reload_number()
    else:
        fill_id_in_text_note()


def fill_id_in_text_note():

    selected_sheet_ids = get_selected_sheet_ids()
    # FixMe
    # Need do change Active_view
    uidoc.Selection.PickObject(UI.Selection.ObjectType.Element, 'Select some element in active view')

    str_sheet_ids = convert_number_for_gap(selected_sheet_ids)
    set_param_on_text_note_on_view_by_name_and_value(doc.ActiveView.Id, 'List_ids', str_sheet_ids)

    reload_number_on_view_by_str_sheet_ids(doc.ActiveView.Id, str_sheet_ids)


def get_selected_sheet_ids():
    """
    Получить список id выбранных в ревите листов

    :return: Список id выбранных видов
    :rtype: List[DB.ElementId]
    """
    sheets = []
    for elem in get_selected():
        if elem.Category.Id == DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_Sheets).Id:
            sheets.append(elem.Id)

    if not sheets:
        raise ScriptError('No sheet is selected. Please select one or several views')

    return sheets


def convert_number_for_gap(sheet_ids, split=', '):
    """
    Получить строку из чисел

    :param sheet_ids: Список чисел
    :type sheet_ids: list[int or str]
    :param split: [Разделитель]
    :type split: str
    :return: Строка с разделителем
    :rtype: str
    """
    return split.join(str(i) for i in sheet_ids)


def decode_number_from_gap(str_numbers, split=', '):
    """
    Получить список чисел из строки

    :param str_numbers: Полученное значение из параметра ревита
    :type str_numbers: str
    :param split: [Разделитель]
    :type split: str
    :return: Список int значений
    :rtype: list[int]
    """
    return [int(i) for i in str_numbers.split(split)]


def get_family_instanse_by_name_and_view_id(name, view_id):
    collector = DB.FilteredElementCollector(doc, view_id).OfClass(DB.FamilyInstance).ToElements()
    for elem in collector:
        if elem.Name == name:
            return elem

    raise ScriptError('View #{} do not have family instance named "{}"'.format(view_id, name))


@transaction
def set_param_on_text_note_on_view_by_name_and_value(view_id, name_param, value_param):
    """
    Заполнения значение параметра у аннотации на виде

    :param view_id: Id вида
    :type view_id: DB.ElementId
    :param name_param: Имя параметра для заполнения
    :type name_param: str
    :param value_param: Значение параметр
    :type value_param: str
    """

    text_note_name = 'КЖ_Общие'
    text_note = get_family_instanse_by_name_and_view_id(text_note_name, view_id)

    param = get_param_elem_by_name(text_note, name_param)
    param.Set(value_param)

    logging.info(
        'Parameter {} on TextNote on view #{} is update on value <{}>'.format(name_param, view_id, value_param))


def reload_number_on_view_by_str_sheet_ids(view_id, str_sheet_ids):
    sheet_numbers = get_sheet_numbers_by_str_sheet_ids(str_sheet_ids)
    str_sheet_number = convert_number_for_gap(sheet_numbers)
    set_param_on_text_note_on_view_by_name_and_value(view_id, 'Номер совместн. листов', str_sheet_number)


def get_param_elem_by_name(elem, param_name):
    """
    Получить параметр элемента по его имени

    :param elem: Элемент
    :type elem: DB.Element
    :param param_name: Имя параметра
    :type param_name: str
    :return: Параметр
    :rtype: DB.Parameter
    """
    return elem.GetParameters(param_name)[0]


def get_param_elem_by_bip(elem, bip):
    """
    Получить параметр элемента по BuiltInParameter

    :param elem: Элемент
    :type elem: DB.Element
    :param bip: Имя BuiltInParameter
    :type bip: DB.BuiltInParameter
    :return: Параметр
    :rtype: DB.Parameter
    """
    return elem.get_Parameter(bip)


def get_sheet_numbers_by_str_sheet_ids(str_sheet_ids):
    """
    Получить номера листов из строки id листов

    :param str_sheet_ids: Строка с id листов
    :type str_sheet_ids: str
    :return: Список с номерами
    :rtype: list[str]
    """
    sheet_ids_int = decode_number_from_gap(str_sheet_ids)
    sheets = get_sheet_from_ids_int(sheet_ids_int)
    sheets_number = get_sheet_numbers_by_sheets(sheets)
    return sheets_number


def get_sheet_from_ids_int(sheet_ids_int):
    """
    Получить листы по int Ids

    :param sheet_ids_int: Список int Id листов
    :type sheet_ids_int: list[int]
    :return: Список листов
    :rtype: list[DB.Sheets]
    """

    res = []
    for str_id in sheet_ids_int:
        sheet_id = DB.ElementId(str_id)
        sheet = doc.GetElement(sheet_id)

        if sheet is None:
            logging.debug('Sheet #{} not found, may be delete'.format(sheet_id))
            continue

        res.append(sheet)
    return res


def get_sheet_numbers_by_sheets(sheets):
    """
    Получить список номеров листов из sheets

    :param sheets: Список листов
    :type sheets: DB.Sheets
    :return: Список с номерами
    :rtype: list[str]
    """
    sheet_numbers = SortedNumbers()

    for sheet in sheets:
        number_param = get_param_elem_by_bip(sheet, DB.BuiltInParameter.SHEET_NUMBER)
        sheet_numbers.append(number_param.AsString())

    return sheet_numbers.get_sorted()


'----------------------------------------'


def reload_number():
    selected_sheet_ids = get_selected_sheet_ids()

    for sheet_id in selected_sheet_ids:
        try:
            str_sheet_ids = get_value_param_by_name_on_text_note_on_view(sheet_id, 'List_ids')
        except ScriptError:
            logging.info('View #{} do not have family "КЖ_Общие"'.format(sheet_id))
            continue

        reload_number_on_view_by_str_sheet_ids(sheet_id, str_sheet_ids)


def get_value_param_by_name_on_text_note_on_view(view_id, name_param):
    text_note_name = 'КЖ_Общие'
    text_note = get_family_instanse_by_name_and_view_id(text_note_name, view_id)

    param = get_param_elem_by_name(text_note, name_param)

    return param.AsString()


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.INFO,
        format='[%(asctime)s] %(levelname).1s <example>: %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S')

    try:
        OUT = main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error')
