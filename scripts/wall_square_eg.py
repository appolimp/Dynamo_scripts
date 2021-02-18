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
WALL_PARAM_ABOUT_ROOM = 'ARO_ROM_Номер сквозной'
WALL_TYPE_PARAM_FINISHING = 'Группа модели'
WALL_TYPE_PARAM_FINISHING_TRUE = 'Вн.От'

LOG = []  # Для сбора ошибок

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
        wall_type_is_finishing_param = wall.WallType.LookupParameter(WALL_TYPE_PARAM_FINISHING)
        if wall_type_is_finishing_param:  # Проверка есть ли у стены такой параметр
            wall_type_is_finishing = wall_type_is_finishing_param.AsString()
            if wall_type_is_finishing and WALL_TYPE_PARAM_FINISHING_TRUE.lower() in wall_type_is_finishing.lower():
                # LOG.append('D. #{} wall is finishing'.format(wall.Id))

                # Получить значение помещения
                wall_param_room = wall.LookupParameter(WALL_PARAM_ABOUT_ROOM)
                # И если оно имеет значение и номер есть в rooms_number_and_material продолжит
                if (wall_param_room and wall_param_room.AsString() and
                        wall_param_room.AsString() in rooms_number_and_material):
                    # LOG.append('D. #{} wall have correct number room'.format(wall.Id))

                    room_materials = rooms_number_and_material[wall_param_room.AsString()]  # Ссылка на словарь комнаты

                    # Получение площади стены
                    wall_area = wall.get_Parameter(DB.BuiltInParameter.HOST_AREA_COMPUTED).AsDouble()
                    # Получение имени материалов стены
                    wall_material_names = get_wall_material_names(wall)
                    for material_name in wall_material_names:
                        room_materials[material_name] = room_materials.get(material_name, 0) + wall_area
            else:
                # LOG.append('E. #{} Wall is not finishing". '.format(wall.Id))
                pass
        else:
            LOG.append('E. #{} Wall do not have parameter "{}". '.format(wall.Id, WALL_TYPE_PARAM_FINISHING) +
                       'To indicate the wall is_finish')

    return rooms_number_and_material


def get_wall_material_names(wall):
    """
    Получить все имена материала слоев стены

    :param wall: Стена
    :type wall: DB.Wall
    :return: Список имен материалов
    :rtype: list[str]
    """

    wall_type = wall.WallType
    com_struct = wall_type.GetCompoundStructure()

    materials_name = set()
    for layer in com_struct.GetLayers():
        material_id = layer.MaterialId
        if material_id != DB.ElementId.InvalidElementId:  # Проверка задан ли материал
            material = doc.GetElement(material_id)
            material_name = material.Name
            materials_name.add(material_name)

    # LOG.append('D. #{} Wall have {} material'.format(wall.Id, len(materials_name)))
    return list(materials_name)


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
                    if param:
                        set_param_depend_type(param, materials[material])  # Заполнение параметра
                        rooms_processed.add(room)  # Для статистики
                        materials_processed.add(material)  # Для статистики
                    else:
                        LOG.append('E Room have not parameter with material name "{}"'.format(param_name))

    TransactionManager.Instance.TransactionTaskDone()  # Транзакция выкл
    return len(rooms_processed), len(materials_processed)  # Для статистики


def set_param_depend_type(param, value):
    """
    Установка значения параметру

    Пытается немного преобразовать данные к нужному типу. Но лучше, чтобы тип параметра и значения совпадал

    :param param: Параметр
    :type param: DB.Parameter
    :param value: Значение
    """

    param_type = param.StorageType  # Тип данных параметра

    if param_type == DB.StorageType.String:
        param.Set(str(value))  # Если ошибка, то не удалось привести значение к str, проверьте тип параметра

    elif param_type == DB.StorageType.Integer:
        param.Set(int(value))  # Если ошибка, то не удалось привести значение к int, проверьте тип параметра

    elif param_type == DB.StorageType.Double:
        param.Set(float(value))  # Если ошибка, то не удалось привести значение к float, проверьте тип параметра

    param.Set(value)  # Если ошибка то тип value и параметра не совпадает


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
    OUT = [main(), LOG]
