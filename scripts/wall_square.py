# coding=utf-8
# #################### Стандартный импорт ###################################

import clr

clr.AddReference('RevitAPI')
clr.AddReference("RevitServices")
clr.AddReference("RevitNodes")

import Autodesk.Revit.DB as DB
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

doc = DocumentManager.Instance.CurrentDBDocument
uidoc = DocumentManager.Instance.CurrentUIApplication.ActiveUIDocument

# #################### Константы ############################################

# Обработка словаря от динамо.
# Связь материала стен и параметра в помещении
WALL_MATERIAL_TO_ROOM_PARAM_FROM_DYNAMO = IN[0]
keys = WALL_MATERIAL_TO_ROOM_PARAM_FROM_DYNAMO.Components()['keys']
values = WALL_MATERIAL_TO_ROOM_PARAM_FROM_DYNAMO.Components()['values']
WALL_MATERIAL_TO_ROOM_PARAM = dict(zip(keys, values))

# Имена пользовательский параметров. Лучше заменить на GUID
WALL_PARAM_ABOUT_ROOM = 'Помещение'
WALL_TYPE_PARAM_FINISHING = 'Отделка'


# #################### Основная логика ######################################


def main():
    """
    Логика:

    - Получаем выбранные пользователем помещения или выбрать все в проекте
    - Получаем выбранные пользователем стены или выбрать все в проекте. Может быть долго, если их ОЧЕНЬ много
    - Заполняем словарь. По помещениям и материалам в них
    - Заполняем соответствующие параметры в помещении

    Работает только с теми материалами стен, которые задал пользователь во входных данных

    """

    # Получение помещений и стен
    rooms = get_selected_or_all(DB.BuiltInCategory.OST_Rooms)
    walls = get_selected_or_all(DB.BuiltInCategory.OST_Walls)

    # Обработка стен
    rooms_number_and_material = get_material_for_room(rooms, walls)

    # Заполнение параметров в помещении
    count_room, count_material = fill_parameters(rooms, rooms_number_and_material)

    return ('Успех.\n'
            'Получено #{} помещений и #{} стен\n'.format(len(rooms), len(walls)) +
            'Обработано: #{} помещений и #{} материалов'.format(count_room, count_material))


def get_material_for_room(rooms, all_wall):
    """
    Заполнить словарь по номерам помещений словарем по материалам в этом помещении

    Учитывает только стены с параметром "Отделка" == "да"

    А так же только те, значение параметра "Помещения" которых есть в выбранных пользователем
    То есть, если пользователь не выбрал помещение с номером "5", эти стены будут игнорироваться

    :param rooms: Список помещений
    :type rooms: list[DB.Room]
    :param all_wall: Список стен
    :type all_wall: list[DB.Wall]
    :return: Словарь номеров помещений и материалов со значениями
    :rtype: dict[str, dict[str, float]]
    """

    rooms_number_and_material = {room.Number: {} for room in rooms}

    for wall in all_wall:

        # Проверка является ли материал отделкой
        wall_type_is_finishing = wall.WallType.LookupParameter(WALL_TYPE_PARAM_FINISHING).AsString()
        if wall_type_is_finishing == 'да':

            # Получить значение помещения
            wall_param_room = wall.LookupParameter(WALL_PARAM_ABOUT_ROOM).AsString()

            # И если оно имеет значение и номер есть в rooms_number_and_material продолжит
            if wall_param_room and wall_param_room in rooms_number_and_material:
                room_material = rooms_number_and_material[wall_param_room]

                # Получение имени материала структуры
                wall_structural_material_id = wall.WallType.get_Parameter(
                    DB.BuiltInParameter.STRUCTURAL_MATERIAL_PARAM).AsElementId()
                wall_structural_material_name = doc.GetElement(wall_structural_material_id).Name

                # Получение площади стены
                wall_area = wall.get_Parameter(DB.BuiltInParameter.HOST_AREA_COMPUTED).AsDouble()

                # Заполнение словаря материалов в помещении. Материал: Значение
                room_material[wall_structural_material_name] = room_material.get(
                    wall_structural_material_name, 0) + wall_area

    return rooms_number_and_material


def fill_parameters(rooms, rooms_number_and_material):
    """
    Заполнить параметры помещения, если для них вычислены значения

    :param rooms: Список помещений, для заполнения параметра
    :type rooms: list[DB.Room]
    :param rooms_number_and_material: Словарь номеров помещений и материалов со значениями
    :type rooms_number_and_material: dict[str, dict[str, float]]
    """

    TransactionManager.Instance.EnsureInTransaction(doc)  # Транзакция вкл

    rooms_processed = set()  # Счетчик для статистики
    materials_processed = set()  # Счетчик для статистики

    for room in rooms:
        if room.Number in rooms_number_and_material:  # Если были стены для этого помещения

            materials = rooms_number_and_material[room.Number]  # Получить словарь его материалов
            for material in materials:

                # Если есть соответствие между материалом стен и параметром в помещении во входных данных
                if material in WALL_MATERIAL_TO_ROOM_PARAM:
                    param_name = WALL_MATERIAL_TO_ROOM_PARAM[material]
                    param = room.LookupParameter(param_name)
                    param.Set(materials[material])  # Заполнение параметра

                    rooms_processed.add(room)  # Для статистики
                    materials_processed.add(material)  # Для статистики

    TransactionManager.Instance.TransactionTaskDone()  # Транзакция выкл
    return len(rooms_processed), len(materials_processed)  # Для статистики


def get_selected_or_all(find_cat):
    """
    Получить выбранные пользователем или все элементы в проекте определенного класса

    :param find_cat: Категории элемента
    :return: Список элементов определенной категории
    :rtype: list
    """

    def get_selected_by_cat(cat):
        """Получить элементы в пользовательском выборе определенной категории"""
        selected_elements = [doc.GetElement(e_id) for e_id in uidoc.Selection.GetElementIds()]
        return [elem for elem in selected_elements if elem.Category.Id == DB.Category.GetCategory(doc, cat).Id]

    preselected = get_selected_by_cat(find_cat)
    if preselected:
        return preselected

    # Получить все элементы в проекте заданной категории
    collector = DB.FilteredElementCollector(doc).OfCategory(find_cat).WhereElementIsNotElementType()
    return list(collector)


# #################### Точка входа ##########################################


if __name__ == '__main__':
    OUT = main()
