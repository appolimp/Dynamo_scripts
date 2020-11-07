# coding=utf-8
from base.wrapper import transaction, doc, DB, app, uidoc, UI
from base.exeption import ScriptError, ElemNotFound
from base.selection import get_selected
from math import pi
from abc import abstractmethod, ABCMeta
from System.Collections.Generic import List

import logging


class MyPoints(object):
    def __init__(self, *points):
        if points and isinstance(points[0], (list, tuple)):
            self.points = points[0]
        else:
            self.points = points

    @classmethod
    def create_rectangle(cls, up, down):
        left_up = DB.XYZ(down.X, up.Y, up.Z)
        right_down = DB.XYZ(up.X, down.Y, up.Z)
        return MyPoints(down, left_up, up, right_down)

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

        return MyPoints(up, down)

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


class MyCalloutBase:
    """
    MetaClass for Callout. Need overrides:

    - _calc_origin_and_orientation
    - _get_symbol_points

    _need_update determines whether to rotate and crop
    """

    __metaclass__ = ABCMeta
    _need_update = True

    def __init__(self, element):
        """
        Initialization of instance

        :param element: DB.Element
        """

        self.element = element

        self._calc_origin_and_orientation()
        self.callout = None

    @abstractmethod
    def _calc_origin_and_orientation(self):
        """
        Calculate origin and orientation of element

        Need be overrides in subclasses
        """

        self.origin = None
        self.orientation = None

    @property
    def rotation(self):
        """
        Angle with sing to Y axis, which the element is rotated [rad]

        :return: Angle
        :rtype: float
        """

        return self.orientation.AngleTo(DB.XYZ.BasisY) * MyPoints.calc_sign(self.orientation, DB.XYZ.BasisY)

    @property
    def _center_instance(self):
        """
        Define of center point instance for move symbol geometry to instance

        :return: DB.XYZ
        """

        return self.origin

    def create_callout_on_view(self, view, rotated, offset=2.0):
        """
        Create callout on given view, offset and rotate if it needed

        :param view: view on which the callout will be created
        :param rotated: Is rotated view or not
        :type rotated: bool
        :param offset: Value of offset at geometry
        :type offset: float
        :return: MyCallout instance
        :rtype: MyCalloutBase
        """

        points = self._get_up_down_points(offset)
        self.callout = MyView.create_callout(view.Id, view.GetTypeId(), *points)

        if self._need_update:
            self._update(symbol_point=points, rotated=rotated)
        return self

    def _update(self, symbol_point, rotated):
        """
        Rotate view if is need and set correct crop border

        :param symbol_point: Max and min point of instance geometry
        :type symbol_point: MyPoints
        :param rotated: Is rotated view or not
        :type rotated: bool
        """

        if rotated:
            self.callout.calc_and_rotate(self.orientation, self.origin)

        border = self.create_border(symbol_point)
        self.callout.set_crop(border)

    def create_border(self, points):
        """
        Create CurveLoop rectangle by two point in main coord system and then rotate it

        :param points: Max and min point
        :type points: MyPoints
        :return: DB.CurveLoop
        """

        points_list = MyPoints.create_rectangle(*points)
        rotated_points = points_list.rot_by_point_and_angle(self.origin, -self.rotation)

        loop = rotated_points.get_curve_loop()
        return loop

    def _get_up_down_points(self, offset):
        """
        Get up_right and left_down points of instance geometry with offset without rotation

        :param offset: Value of offset at geometry
        :type offset: float
        :return: Points max and min of instance geometry
        :rtype: MyPoints
        """

        points = self._get_symbol_points()
        points.transform_symbol_point_for_callout(self._center_instance, offset)
        return points

    @abstractmethod
    def _get_symbol_points(self):
        """
        Get up_right and left_down points of symbol geometry

        Need be overrides in subclasses

        :return: Points max and min of symbol geometry
        :rtype: MyPoints
        """

        up, down = DB.XYZ(), DB.XYZ()
        return MyPoints(up, down)

    def _get_symbol_points_as_solid(self):
        """
        Get corner points via getting symbol solid and get it BoundingBox

        :return: Points max and min of symbol solid
        :rtype: MyPoints
        """

        solid = GeometryInRevit.get_solid_by_elem(self.element.Symbol)
        box = solid.GetBoundingBox()
        return MyPoints(box.Max, box.Min)


class ColumnCallout(MyCalloutBase):
    """Class for create callout to structural column"""

    def _calc_origin_and_orientation(self):
        """Calculate origin and orientation of element via location point and param orientation"""

        self.origin = self.element.Location.Point
        self.orientation = self.element.FacingOrientation

    def _get_symbol_points(self):
        """
        Get points of symbol geometry to create callout: max and min

        Overrides method in metaclass

        :return: Points max and min
        :rtype: MyPoints
        """

        return self._get_symbol_points_as_solid()


class WallCallout(MyCalloutBase):
    """Class for create callout to wall"""

    def _calc_origin_and_orientation(self):
        """Calculate origin and orientation of element via location curve"""

        first, second = self.element.Location.Curve.GetEndPoint(0), self.element.Location.Curve.GetEndPoint(1)
        self.origin = (first + second) / 2.0
        self.orientation = self.element.Location.Curve.Direction

    def _get_symbol_points(self):
        """
        Get points of symbol geometry to create callout: via curve location and width

        Overrides method in metaclass

        :return: Points max and min
        :rtype: MyPoints
        """

        width = self._width
        length = self.element.Location.Curve.Length

        up, down = DB.XYZ(width / 2.0, length / 2.0, 0), DB.XYZ(-width / 2.0, -length / 2.0, 0)
        return MyPoints(up, down)

    @property
    def _width(self):
        """
        Return width of wall via it parameter

        :return: Width
        :rtype: float
        """

        return self.element.Width


class BeamCallout(WallCallout):
    """Class for create callout to beam"""

    @property
    def _width(self):
        """
        Return width of beam via symbol point distance

        :return: Width
        :rtype: float
        """

        up, down = self._get_symbol_points_as_solid()
        return up.Y - down.Y


class FloorCallout(MyCalloutBase):
    """Class for create callout to floor and foundation"""

    def _calc_origin_and_orientation(self):
        """Calculate origin and orientation of element via it upper face"""

        self.up_face = self._get_up_face()
        self.origin = self.up_face.origin
        self.orientation = self.up_face.orientation

        logging.debug('Origin: {:.3f}, {:.3f}, {:.3f}'.format(
            self.origin.X, self.origin.Y, self.origin.Z))

        logging.debug('Orient: {:.3f}, {:.3f}, {:.3f}'.format(
            self.orientation.X, self.orientation.Y, self.orientation.Z))

    def _get_up_face(self):
        """
        Get upper face of element

        :return: Upper face of element
        :rtype: MyFace
        """

        solid = GeometryInRevit.get_solid_by_elem(self.element)

        for face in solid.Faces:
            if face.FaceNormal.IsAlmostEqualTo(DB.XYZ.BasisZ, 0.001):
                return MyFace(face).calc_param()

        raise ElemNotFound('Face up not found')

    def _get_symbol_points(self):
        """
        Get points of symbol geometry to create callout: via face

        Overrides method in metaclass

        :return: Points max and min
        :rtype: MyPoints
        """

        return self.up_face.get_two_point()


class AnyCallout(MyCalloutBase):
    """
    Class for create callout to anything element

    Get corner point via BoundingBox, so it maybe non correct in not orthogonal view

    _need_update == False, so not update rotate and crop
    """

    _need_update = False

    def _calc_origin_and_orientation(self):
        """Calculate origin and orientation of element

        For any element it is unnecessary"""

    @property
    def _center_instance(self):
        """
        Origin of instance need for transform symbol geometry to instance

        In this case it unnecessary, so it equal 0

        :return: DB.XYZ.Zero
        """

        return DB.XYZ.Zero

    def _get_symbol_points(self):
        """
        Get points of symbol geometry to create callout: via BoundingBox

        In this case get points of instance geometry

        Overrides method in metaclass

        :return: Points max and min
        :rtype: MyPoints
        """

        view = doc.ActiveView
        box = self.element.get_BoundingBox(view)
        return MyPoints(box.Max, box.Min)


class MyCalloutFactory(object):
    """
    Factory to create callout

    It check the category and selects the desired class or default

    Developed categories:

    - StructuralColumns
    - Walls
    - StructuralFraming (beams)
    - Floors
    - StructuralFoundation

    """

    VALID_CAT = {
        DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_StructuralColumns).Id: ColumnCallout,
        DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_Walls).Id: WallCallout,
        DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_StructuralFraming).Id: BeamCallout,
        DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_Floors).Id: FloorCallout,
        DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_StructuralFoundation).Id: FloorCallout
    }
    DEFAULT = AnyCallout

    @classmethod
    def get_callout_to_element(cls, element):
        """
        Get callout creator instance depending on category

        :param element: DB.Element
        :return: instance of class callout
        """

        elem_cat_id = element.Category.Id

        if elem_cat_id in cls.VALID_CAT:
            logging.info('Get category: {}'.format(element.Category.Name))
            return cls.VALID_CAT[elem_cat_id](element)

        logging.error('Not valid category: {}'.format(element.Category.Name))
        return cls.DEFAULT(element)


class MyView:
    """
    My view class with features:

    - crop view by CurveLoop
    - rotate view about z axis by point and angle
    - create callout
    """

    def __init__(self, view):
        """
        Initialization of instance

        :param view: DB.View
        """

        self.view = view

    @classmethod
    def create_callout(cls, view_id, view_type_id, first_point=DB.XYZ(0, 0, 0), second_point=DB.XYZ(10, 10, 0)):
        """
        Create callout on view by params

        :param view_id: parentViewId
        :param view_type_id: viewFamilyTypeId
        :param first_point: DB.XYZ
        :param second_point: DB.XYZ

        :return: Created callout
        :rtype: MyView
        """

        callout = DB.ViewSection.CreateCallout(doc, view_id, view_type_id, first_point, second_point)
        logging.info('Callout "{} #{}" was created'.format(callout.Name, callout.Id))
        return cls(callout)

    def set_crop(self, borders):
        """
        Set crop view to given borders as CurveLoop

        :param borders: DB.CurveLoop
        """

        view_manage = self.view.GetCropRegionShapeManager()
        view_manage.SetCropShape(borders)
        logging.info('Set crop for view: {}'.format(self.view.Name))

    def calc_and_rotate(self, elem_dir, origin):
        """
        Calculate angle of rotation between current view and UpDirection of ActiveView

        And if necessary rotate view to vertical or horizontal direction

        :param elem_dir: DB.XYZ, direction view to
        :param origin: DB.XYZ, origin of view, about the center of which will rotate
        """

        angle = CoolFeature.calc_angle_to_ver_or_hor_side(elem_dir, second_vector=self.view.UpDirection)

        if 0.02 < abs(angle) < pi - 0.02:  # 0.02 == 1 градус
            self._rotate_view(-angle, origin)

    def _rotate_view(self, angle, point):
        """
        Rotate view by angle about point and z axis

        :param angle: angle to rotation
        :type angle: float
        :param point: DB.XYZ, point about which view will rotate
        """

        crop_elem = self._find_crop_elem()
        axis = DB.Line.CreateBound(point, point + DB.XYZ.BasisZ)

        DB.ElementTransformUtils.RotateElement(doc, crop_elem, axis, angle)
        logging.debug('View was rotated to {:.2f}'.format(angle * 180 / pi))

    def _find_crop_elem(self):
        """
        For current view find crop element, which we can rotate or move

        :return: DB.Element, crop element on view
        """

        cat_filter = DB.ElementCategoryFilter(DB.BuiltInCategory.OST_Viewers)
        elems = self.view.GetDependentElements(cat_filter)
        return elems[0]

    def __getattr__(self, item):
        """
        Parameters stub
        """
        return getattr(self.view, item)


class CoolFeature(object):

    @staticmethod
    def calc_angle_to_ver_or_hor_side(main_vector, second_vector):
        """
        Calc angle between main and second

        Then transform it to main vector or it perpendicular and make angle less than 90

        :param main_vector: DB.XYZ
        :param second_vector: DB.XYZ, for example UpDirection of view
        :return: Angle between main and second < 90
        :rtype: float
        """

        angle = main_vector.AngleTo(second_vector)
        logging.debug('Calc first rotation angle: {:.2f}'.format(angle * 180 / pi))

        if pi / 4 < angle <= pi / 2:
            angle -= pi / 2
        elif pi / 2 < angle <= 3 * pi / 4:
            angle += pi / 2 - pi
        elif 3 * pi / 4 < angle <= pi:
            angle -= pi

        logging.debug('Calc change rotation angle: {:.2f}'.format(angle * 180 / pi))
        sign_angle = MyPoints.calc_sign(main_vector, second_vector) * angle

        logging.debug('Calc sign rotation angle: {:.2f}'.format(sign_angle * 180 / pi))
        return sign_angle


class GeometryInRevit(object):
    """
    Work with geometry of Revit Element:

    - Get solid of instance
    """

    @classmethod
    def get_solid_by_elem(cls, element):
        """
        Get instance solid for given element

        :param element: DB.Element
        :return: DB.Solid
        """

        option = cls.create_option()
        geometry = element.get_Geometry(option)
        for elem in geometry:
            if type(elem) is DB.Solid and elem.Volume:
                logging.debug('Get Solid')
                return elem

        raise ElemNotFound('Valid solid not found {}')

    @staticmethod
    def create_option():
        """
        Create user preferences for parsing of geometry

        In this case View == None, get References == True

        :return: DB.Options
        """

        opt = app.Create.NewGeometryOptions()
        opt.ComputeReferences = True

        logging.debug('Option create')
        return opt


@transaction
def main():
    """
    Create Callout to selected elements

    Get pre-selected elements or invite user to select it

    Get input from dynamo:

    - OFFSET: type(float), Offset value to callout
    - ROTATED: type(bool), Rotate or not callout view
    """

    elems = get_preselected_elems_or_invite()
    OFFSET = IN[0]
    ROTATED = IN[1]

    for elem in elems:
        cal = MyCalloutFactory.get_callout_to_element(elem)
        cal.create_callout_on_view(doc.ActiveView, rotated=ROTATED, offset=OFFSET)


def get_preselected_elems_or_invite():
    """
    Get list pre-selected elements or invite user to select

    :return: List of selected elements
    :rtype: list
    """

    selected = get_selected(as_list=True)
    if selected:
        return selected

    ref_elem = uidoc.Selection.PickObject(UI.Selection.ObjectType.Element)
    elem = doc.GetElement(ref_elem.ElementId)
    return [elem]


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.DEBUG,
        format='[%(asctime)s] %(levelname).1s: %(message)s',
        datefmt='%M:%S')

    try:
        main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error')
