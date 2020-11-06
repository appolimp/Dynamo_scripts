# coding=utf-8
from base.wrapper import transaction, doc, DB, app, uidoc, UI
from base.exeption import ScriptError, ElemNotFound
from base.selection import get_selected
from math import pi
from abc import abstractmethod, ABCMeta
from System.Collections.Generic import List

import logging


class MyPoints(object):
    def __init__(self, points):
        self.points = points

    @classmethod
    def create_rectangle(cls, up, down):
        left_up = DB.XYZ(down.X, up.Y, up.Z)
        right_down = DB.XYZ(up.X, down.Y, up.Z)
        return MyPoints([down, left_up, up, right_down])

    def rot_by_point_and_angle(self, origin, angle):
        transform = DB.Transform.CreateRotationAtPoint(DB.XYZ.BasisZ, angle, origin)
        new_points = [transform.OfPoint(point) for point in self.points]

        return MyPoints(new_points)

    def get_curve_loop(self):
        loop_list = List[DB.Curve]()

        for first, second in zip(self.points, self.points[1:] + [self.points[0]]):
            loop_list.Add(DB.Line.CreateBound(first, second))

        loop = DB.CurveLoop.Create(loop_list)
        logging.debug('CurveLoop was created')
        return loop

    def move_by_vector(self, vector):
        self.points = [point + vector for point in self.points]
        return self

    def set_height(self, height):
        self.points = [DB.XYZ(point.X, point.Y, height) for point in self.points]
        return self

    def displace_two_point_to_vector(self, vector):
        first, second = self.points
        self.points = [first + vector, second - vector]
        return self

    def transform_symbol_point_for_callout(self, origin, offset):
        self.move_by_vector(origin)
        self.set_height(doc.ActiveView.Origin.Z)
        self.displace_two_point_to_vector(DB.XYZ(offset, offset, 0))

    @staticmethod
    def calc_sign(main_v, second):
        prod = main_v.CrossProduct(second)
        return 1 if prod.Z >= 0 else -1

    def compute_min_max(self):
        max_x = max_y = float('-inf')
        min_x = min_y = float('inf')

        for point in self.points:
            max_x = max(point.X, max_x)
            max_y = max(point.Y, max_y)
            min_x = min(point.X, min_x)
            min_y = min(point.Y, min_y)

        up = DB.XYZ(max_x, max_y, 0)
        down = DB.XYZ(min_x, min_y, 0)

        return MyPoints([up, down])

    def __str__(self):
        return 'Point: ' + str(self.points)

    def __format__(self, format_spec):
        return '\nPoints:\n' + '\n'.join(
            '{:.2f}, {:.2f}, {:.2f}'.format(point.X, point.Y, point.Z) for point in self.points)

    def __iter__(self):
        return iter(self.points)

    def __getattr__(self, item):
        return getattr(self.points, item)

    def __getitem__(self, item):
        return self.points[item]


class MyFace:
    def __init__(self, face):
        self.face = face

    def calc_param(self):
        self._find_corner()
        self._compute_center()
        self.orientation = self.face.YVector
        self.rotation = -self.orientation.AngleTo(DB.XYZ.BasisY) * MyPoints.calc_sign(self.orientation, DB.XYZ.BasisY)
        return self

    def get_two_point(self):
        if 0.02 < abs(self.rotation) < pi - 0.02:
            rot_point = self.corner_polygon.rot_by_point_and_angle(self.origin, -self.rotation)
        else:
            rot_point = self.corner_polygon

        rot_point.move_by_vector(-self.origin)
        return rot_point.compute_min_max()

    def _find_corner(self):
        loops = self.face.EdgeLoops
        bounds = self._get_bounds(loops)

        area = []
        for f_bounds in self.flatten_polygons(bounds):
            area.append(self.get_signed_polygon_area(f_bounds))

        self._area = min(area)
        self.corner_polygon = MyPoints(bounds[area.index(self._area)])

        logging.debug('Calc area: {}'.format(self._area))
        # logging.debug('{}'.format(self.corner_polygon))

        return self.corner_polygon

    def _compute_center(self):
        g_x_sum = 0
        g_y_sum = 0

        for first, second in zip(self.corner_polygon, self.corner_polygon[1:] + [self.corner_polygon[0]]):
            sec_br = first.X * second.Y - second.X * first.Y
            g_x_sum += (first.X + second.X) * sec_br
            g_y_sum += (first.Y + second.Y) * sec_br

        g_x_sum /= 6 * -self._area
        g_y_sum /= 6 * -self._area

        self.origin = DB.XYZ(g_x_sum, g_y_sum, 0)
        # logging.debug('Calc origin: {:.3}, {:.3}, {:.3}'.format(self.origin.X, self.origin.Y, self.origin.Z))
        return self.origin

    @staticmethod
    def _get_bounds(loops):
        polygons = []
        for loop in loops:
            polygon = []
            for edge in loop:
                points = list(edge.Tessellate())
                if polygon:
                    assert not polygon[-1].IsAlmostEqualTo(points[0])
                polygon.extend(points[:-1])
            polygons.append(polygon)
        return polygons

    def flatten_polygons(self, polygons):
        """
        Спроецировать список полигонов на горизонтальную плоскость

        :param polygons: Список полигонов
        :type polygons: list[list[DB.XYZ]]
        :return: Лист плоских точек
        :rtype: list[list[DB.UV]]
        """

        return List[List[DB.UV]](self.flatten_polygon(polygon) for polygon in polygons)

    def flatten_polygon(self, polygon):
        """
        Спроецировать список точек на горизонтальную плоскость

        :param polygon: Лист точек
        :type polygon: list[DB.XYZ]
        :return: Лист плоских точек
        :rtype: list[DB.UV]
        """

        return List[DB.UV](self.flatten_point(point) for point in polygon)

    @staticmethod
    def flatten_point(point):
        """
        Спроецировать точку на горизонтальную плоскость как вектор в двумерном пространстве

        :param point: Point
        :type point: DB.XYZ
        :return: new DB.UV
        :rtype: DB.UV
        """

        return DB.UV(point.X, point.Y)

    @staticmethod
    def get_signed_polygon_area(points):
        """
        Get area 2d polygon

        :param points: list[DB.UV]
        :type points: list[DB.UV]
        :return: Area
        :rtype: float
        """

        area = 0
        j = points[len(points) - 1]

        for i in points:
            area += (j.U + i.U) * (j.V - i.V)
            j = i

        return area / 2


class CreateCallout:
    def __init__(self, element):
        self.element = element

    @classmethod
    def to_element(cls, element, rotated, offset):
        inst = cls(element)
        callout = inst.create(rotated, offset)
        return callout

    def create(self, rotated, offset):
        view = doc.ActiveView
        valid_cat = {
            DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_StructuralColumns).Id: ColumnCallout,
            DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_Walls).Id: WallCallout,
            DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_StructuralFraming).Id: BeamCallout,
            DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_Floors).Id: FloorCallout,
            DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_StructuralFoundation).Id: FloorCallout
        }

        elem_cat_id = self.element.Category.Id
        if elem_cat_id in valid_cat:
            logging.info('Get category: {}'.format(self.element.Category.Name))
            callout = valid_cat[elem_cat_id](self.element).create_callout_on_view(view, rotated, offset)
        else:
            logging.error('not valid category: {}'.format(self.element.Category.Name))
            up, down = self._get_points(offset)
            callout = DB.ViewSection.CreateCallout(doc, view.Id, view.GetTypeId(), up, down)

        return callout

    def _get_points(self, offset):
        view = doc.ActiveView
        box = self.element.get_BoundingBox(view)
        points = MyPoints([box.Max, box.Min])
        points.transform_symbol_point_for_callout(DB.XYZ.Zero, offset)
        return points


class ElemCallout:
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, element):
        self.element = element
        self.origin = None
        self.orientation = None
        self.callout = None
        self._need_update = True

    @property
    def rotation(self):
        return - self.orientation.AngleTo(DB.XYZ.BasisY) * MyPoints.calc_sign(self.orientation, DB.XYZ.BasisY)

    def create_callout_on_view(self, view, rotated, offset):
        points = self._get_up_down_points(offset)
        self.callout = MyView.create_callout(view.Id, view.GetTypeId(), *points)

        if self._need_update:
            self._update(symbol_point=points, rotated=rotated)
        return self

    def _update(self, symbol_point, rotated):
        if rotated:
            self.callout.calc_and_rotate(self.orientation, self.origin)

        borders = self.create_borders(symbol_point)
        self.callout.set_crop(borders)

    def create_borders(self, points):
        points_list = MyPoints.create_rectangle(*points)
        rotated_points = points_list.rot_by_point_and_angle(self.origin, self.rotation)

        loop = rotated_points.get_curve_loop()
        return loop

    def _get_up_down_points(self, offset):
        points = self._get_symbol_points()
        points.transform_symbol_point_for_callout(self.origin, offset)
        return points

    @abstractmethod
    def _get_symbol_points(self):
        up, down = DB.XYZ(), DB.XYZ()
        return MyPoints([up, down])

    @staticmethod
    def create_option():
        opt = app.Create.NewGeometryOptions()
        logging.debug('Option create')
        return opt

    def _get_symbol_points_as_solid(self):
        solid = self._get_solid_by_elem(self.element.Symbol)
        box = solid.GetBoundingBox()
        up, down = box.Max, box.Min
        return MyPoints([up, down])

    def _get_solid_by_elem(self, geom_elem):
        opt = self.create_option()
        geometry = geom_elem.get_Geometry(opt)

        for elem in geometry:
            if type(elem) is DB.Solid and elem.Volume:
                logging.debug('Get Solid')
                return elem

        raise ScriptError('Valid solid not found {}')


class ColumnCallout(ElemCallout):
    def __init__(self, column):
        super(ColumnCallout, self).__init__(column)

        self.origin = column.Location.Point
        self.orientation = column.FacingOrientation

    def _get_symbol_points(self):
        return self._get_symbol_points_as_solid()


class WallCallout(ElemCallout):
    def __init__(self, wall):
        super(WallCallout, self).__init__(wall)

        first, second = wall.Location.Curve.GetEndPoint(0), wall.Location.Curve.GetEndPoint(1)
        self.origin = (first + second) / 2.0
        self.orientation = wall.Location.Curve.Direction

    def _get_symbol_points(self):
        width = self._width
        length = self.element.Location.Curve.Length

        up, down = DB.XYZ(width/2.0, length/2.0, 0), DB.XYZ(-width/2.0, -length/2.0, 0)

        return MyPoints([up, down])

    @property
    def _width(self):
        return self.element.Width


class BeamCallout(WallCallout):
    @property
    def _width(self):
        up, down = self._get_symbol_points_as_solid()
        return up.Y - down.Y


class FloorCallout(ElemCallout):
    def __init__(self, floor):
        super(FloorCallout, self).__init__(floor)
        self._calc_origin_and_orientation()

    def _calc_origin_and_orientation(self):
        solid = self._get_solid_by_elem(self.element)
        self.up_face = self._get_up_face(solid.Faces)

        self.origin = self.up_face.origin
        self.orientation = self.up_face.orientation

        logging.debug('Origin: {:.3f}, {:.3f}, {:.3f}'.format(self.origin.X, self.origin.Y, self.origin.Z))
        logging.debug('Orient: {:.3f}, {:.3f}, {:.3f}'.format(self.orientation.X, self.orientation.Y, self.orientation.Z))

    @staticmethod
    def _get_up_face(faces):
        for face in faces:
            if face.FaceNormal.IsAlmostEqualTo(DB.XYZ.BasisZ, 0.001):
                return MyFace(face).calc_param()
        raise ElemNotFound('Face up not found')

    def _get_symbol_points(self):
        points = self.up_face.get_two_point()
        return points


class AnyCallout(MyCalloutBase):
    def __init__(self, element):
        super(AnyCallout, self).__init__(element)
        self._need_update = False

    def _get_up_down_points(self, offset):
        points = self._get_symbol_points()
        points.transform_symbol_point_for_callout(DB.XYZ.Zero, offset)

        return points

    def _get_symbol_points(self):
        return self._get_as_bounding_box()

    def _get_as_bounding_box(self):
        view = doc.ActiveView
        box = self.element.get_BoundingBox(view)
        return MyPoints([box.Max, box.Min])
class MyView:
    def __init__(self, view):
        self.view = view

    @classmethod
    def create_callout(cls, view_id, view_type_id, first_point=DB.XYZ(0, 0, 0), second_point=DB.XYZ(10, 10, 0)):
        callout = DB.ViewSection.CreateCallout(doc, view_id, view_type_id, first_point, second_point)
        logging.info('Callout "{} #{}" was created'.format(callout.Name, callout.Id))
        return cls(callout)

    def set_crop(self, borders):
        view_manage = self.view.GetCropRegionShapeManager()
        view_manage.SetCropShape(borders)
        logging.info('Set crop for view')

    def calc_and_rotate(self, elem_dir, origin):
        angle = self._calc_angle(elem_dir)
        if 0.02 < abs(angle) < pi - 0.02:  # 0.02 == 1 градус
            self._rotate_view(angle, origin)

    def _calc_angle(self, elem_dir):
        view_dir = self.view.UpDirection
        angle = elem_dir.AngleTo(view_dir)

        logging.debug('Calc first rotation angle: {:.2f}'.format(angle * 180 / pi))

        if pi / 4 < angle <= pi / 2:
            angle -= pi / 2
        elif pi / 2 < angle <= 3 * pi / 4:
            angle += pi / 2 - pi
        elif 3 * pi / 4 < angle <= pi:
            angle -= pi

        logging.debug('Calc change rotation angle: {:.2f}'.format(angle * 180 / pi))
        sign_angle = MyPoints.calc_sign(view_dir, elem_dir) * angle

        logging.debug('Calc sign rotation angle: {:.2f}'.format(sign_angle * 180 / pi))
        return sign_angle

    def _rotate_view(self, angle, origin):
        crop_elem = self._find_crop_elem()
        axis = DB.Line.CreateBound(origin, origin + DB.XYZ.BasisZ)

        DB.ElementTransformUtils.RotateElement(doc, crop_elem, axis, angle)
        logging.debug('View was rotated'.format(angle))

    def _find_crop_elem(self):
        cat_filter = DB.ElementCategoryFilter(DB.BuiltInCategory.OST_Viewers)
        elems = self.view.GetDependentElements(cat_filter)

        return elems[0]

    def __getattr__(self, item):
        return getattr(self.view, item)


@transaction
def main():
    elems = get_elems()
    OFFSET = IN[0]
    ROTATED = IN[1]

    for elem in elems:
        CreateCallout.to_element(elem, rotated=ROTATED, offset=OFFSET)


def get_elems():
    selected = get_selected(as_list=True)
    if selected:
        return selected

    ref_elem = uidoc.Selection.PickObject(UI.Selection.ObjectType.Element)
    elem = doc.GetElement(ref_elem.ElementId)
    return [elem]


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.DEBUG,
        format='[%(asctime)s] %(levelname).1s <example>: %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S')

    try:
        main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error')
