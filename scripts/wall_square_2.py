# coding=utf-8
import clr

clr.AddReference('RevitAPI')
clr.AddReference("RevitServices")

import Autodesk.Revit.DB as DB
from RevitServices.Persistence import DocumentManager

doc = DocumentManager.Instance.CurrentDBDocument
uidoc = DocumentManager.Instance.CurrentUIApplication.ActiveUIDocument


def main():
    """
    Получение площади отделки помещений

    - Получение выбранных помещений или все в проекте
    - Расчет площади финишной отделки

    # FIXME Вычисляет полную площадь (окна и двери не учитываются)

    :return: Список помещений из Id помещения и словаря с материалами и площадью
    :rtype: list[int, dict[DB.Material, float]]
    """

    rooms = get_selected_or_all(DB.BuiltInCategory.OST_Rooms)
    room_materials_and_values = calc_material(rooms)

    rooms_id = [room.Id for room in rooms]
    return list(zip(rooms_id, room_materials_and_values))


def get_selected_by_cat(cat):
    """Получить элементы в пользовательском выборе определенной категории"""
    selected_elements = [doc.GetElement(e_id) for e_id in uidoc.Selection.GetElementIds()]
    return [elem for elem in selected_elements if elem.Category.Id == DB.Category.GetCategory(doc, cat).Id]


def get_selected_or_all(find_class):
    """
    Получить выбранные пользователем или все элементы в проекте определенного класса

    :param find_class: Класс элемента
    :return: Список элементов определенного класса
    :rtype: list
    """

    preselected = get_selected_by_cat(find_class)
    if preselected:
        return preselected

    collector = DB.FilteredElementCollector(doc).OfCategory(find_class).WhereElementIsNotElementType()
    rooms = list(collector)
    return rooms


def calc_material(rooms):
    """
    Вычисление материалов финишной отделки помещений

    https://forum.dynamobim.com/t/getting-finishing-material-inside-of-the-room/11528/2

    # FIXME Вычисляет полную площадь (окна и двери не учитываются)

    :param rooms:
    :type rooms: list[DB.Room]
    :return: Список словарей, где ключ имя материала, а значение - площадь
    :rtype: list[dict[str, float]]
    """

    calculator = DB.SpatialElementGeometryCalculator(doc)
    rooms_materials = []

    for room in rooms:
        if room.Volume <= 0.01:
            continue

        result = calculator.CalculateSpatialElementGeometry(room)
        room_solid = result.GetGeometry()

        room_material = {}
        for face in room_solid.Faces:
            for sub_face in result.GetBoundaryFaceInfo(face):
                if sub_face.SubfaceType == DB.SubfaceType.Side:
                    bounding_element_face = sub_face.GetBoundingElementFace()

                    area = bounding_element_face.Area
                    material_id = bounding_element_face.MaterialElementId
                    material_name = doc.GetElement(material_id).Name

                    room_material[material_name] = room_material.get(material_name, 0) + area * 0.3048 * 0.3048

        rooms_materials.append(room_material)

    return rooms_materials


if __name__ == '__main__':
    OUT = main()
