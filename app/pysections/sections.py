# sections.py
#
# A Python library for cross-sectional properties calculation.
# Copyright (C) 2025  Cristian Danilo Ramírez Vargas
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ---------------------------------------------------------------------
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from abc import ABC, abstractmethod

plt.style.use('ggplot')


class Section:
    def _A(self, points):
        A = 0
        num_points = np.shape(points)[0]

        for i in range(num_points):
            Ai = (points[i, 0] * points[(i + 1) % num_points, 1] - 
                  points[i, 1] * points[(i + 1) % num_points, 0])
            Ai*=0.5

            A+=Ai

        return A

    def _Qx(self, points):
        Qx = 0
        num_points = np.shape(points)[0]
        
        for i in range(num_points):
            Qxi = (points[i, 0] * points[(i + 1) % num_points, 1] - 
                   points[i, 1] * points[(i + 1) % num_points, 0])
            Qxi*= (points[i, 1] + points[(i + 1) % num_points, 1]) / 6
            
            Qx+=Qxi
        
        return Qx

    def _Qy(self, points):
        Qy = 0        
        num_points = np.shape(points)[0]
        
        for i in range(num_points):
            Qyi = (points[i, 0] * points[(i + 1) % num_points, 1] - 
                   points[i, 1] * points[(i + 1) % num_points, 0])
            Qyi*= (points[i, 0] + points[(i + 1) % num_points, 0]) / 6
            
            Qy+=Qyi
        
        return Qy

    def _x(self, points):
        return self._Qy(points) / self._A(points)
    
    def _y(self, points):
        return self._Qx(points) / self._A(points)

    def _Ixx(self, points):
        Ixx = 0
        y = self._y(points)

        num_points = np.shape(points)[0]

        for i in range(num_points):
            Ai = (points[i, 0] * points[(i + 1) % num_points, 1] - 
                  points[i, 1] * points[(i + 1) % num_points, 0])
            Ai*=0.5
            
            yi = (points[i, 1] + points[(i + 1) % num_points, 1]) / 3

            Ixxi = (Ai / 6) * \
                (points[i, 1] ** 2 +
                 points[i, 1] * points[(i + 1) % num_points, 1] +
                 points[(i + 1) % num_points, 1] ** 2)
            Ixx+=(Ixxi + Ai * y * (y - 2 * yi))

        return Ixx

    def _Iyy(self, points):
        Iyy = 0
        x = self._x(points)

        num_points = np.shape(points)[0]

        for i in range(num_points):
            Ai = (points[i, 0] * points[(i + 1) % num_points, 1] -
                  points[i, 1] * points[(i + 1) % num_points, 0])
            Ai*=0.5

            xi = (points[i, 0] + points[(i + 1) % num_points, 0]) / 3

            Iyyi = (Ai / 6) * \
                (points[i, 0] ** 2 +
                 points[i, 0] * points[(i + 1) % num_points, 0] +
                 points[(i + 1) % num_points, 0] ** 2)
            Iyy+=(Iyyi + Ai * x * (x - 2 * xi))

        return Iyy


class _SinglePolygonSection(ABC, Section):
    def __init__(self):
        super().__init__()
        self._points = self._calculate_points()

    @abstractmethod
    def _calculate_points(self):
        pass

    @property
    def points(self):
        return self._points
        
    @property
    def area(self):
        return super()._A(self.points)

    # @property
    # def section_modulus_y(self):
    #     return super()._Qx(self.points)

    # @property
    # def section_modulus_z(self):
    #     return super()._Qy(self.points)

    @property
    def y(self):
        return super()._x(self.points)

    @property
    def z(self):
        return super()._y(self.points)

    @property
    def Iyy(self):
        return super()._Ixx(self.points)

    @property
    def Izz(self):
        return super()._Iyy(self.points)


class BulbTeeGirderBridge(_SinglePolygonSection):
    def __init__(self, b1, b2, b3, b4, d1, d2, d3, d4, d5, d6, d7, t1, t2, c1):
        self.b1 = b1
        self.b2 = b2
        self.b3 = b3
        self.b4 = b4
        
        self.d1 = d1
        self.d2 = d2
        self.d3 = d3
        self.d4 = d4
        self.d5 = d5
        self.d6 = d6
        self.d7 = d7
        
        self.t1 = t1
        self.t2 = t2

        self.c1 = c1

        super().__init__()

    def _calculate_points(self):
        pts = np.zeros((18, 2), dtype=float)

        pts[0, 0] = self.b2 / 2 - self.c1
        pts[0, 1] = 0

        pts[1, 0] = self.b2 / 2
        pts[1, 1] = self.c1

        pts[2, 0] = pts[1, 0]
        pts[2, 1] = self.d5

        pts[3, 0] = self.t2 / 2 + self.b4
        pts[3, 1] = self.d5 + self.d6

        pts[4, 0] = self.t2 / 2 
        pts[4, 1] = self.d5 + self.d6 + self.d7

        pts[5, 0] = self.t1 / 2
        pts[5, 1] = self.d1 - (self.d2 + self.d3 + self.d4)

        pts[6, 0] = self.t1 / 2 + self.b3
        pts[6, 1] = self.d1 - (self.d2 + self.d3)

        pts[7, 0] = self.b1 / 2
        pts[7, 1] = self.d1 - self.d2

        pts[8, 0] = pts[7, 0]
        pts[8, 1] = self.d1

        # simetría
        for i in range(9):
            pts[17 - i, 0] = -pts[i, 0]
            pts[17 - i, 1] =  pts[i, 1]
    
        # eliminar duplicados consecutivos (con tolerancia)
        unique = []
        for row in pts:
            if not unique:
                unique.append(row.copy())
            else:
                if not np.allclose(row, unique[-1], atol=1e-12, rtol=1e-9):
                    unique.append(row.copy())
        
        return np.vstack(unique)

    @property
    def height(self):
        return self.d1
    
    @property
    def zi(self):
        return self.z

    @property
    def zs(self):
        return self.height - self.zi
    
    @property
    def wi(self):
        return self.Iyy / self.zi

    @property
    def ws(self):
        return self.Iyy / self.zs

    def plot(self, filename=None):
        pts = self.points
        x = np.append(pts[:, 0], pts[0, 0])
        y = np.append(pts[:, 1], pts[0, 1])

        plt.figure()
        plt.plot(x, y, color='black', linewidth=1)
        plt.fill(x, y, 'lightgray', alpha=0.4)
        plt.scatter(x, y, color='red')

        plt.grid(True, 'both')
        plt.minorticks_on()
        ax = plt.gca()
        ax.set_aspect('equal', adjustable='box')
        ax.xaxis.set_major_locator(ticker.MultipleLocator(0.2))
        ax.yaxis.set_major_locator(ticker.MultipleLocator(0.2))

        if filename:
            plt.savefig(filename, bbox_inches='tight', pad_inches=0)
        else:
            plt.show()


class Deck(_SinglePolygonSection): 
    def __init__(self, width, thickness):
        self.width = width
        self.thickness = thickness
        
        super().__init__()

    def _calculate_points(self):
        pts = np.zeros((4, 2), dtype=float)
        
        pts[0, 0] = self.width / 2
        pts[0, 1] = 0  
        
        pts[1, 0] = self.width / 2
        pts[1, 1] = self.thickness
        
        pts[2, 0] = -self.width / 2
        pts[2, 1] = self.thickness
        
        pts[3, 0] = -self.width / 2
        pts[3, 1] = 0  
        
        return pts

    @property
    def height(self):
        return self.thickness


class BoxGirderBridge(Section):
    def __init__(self, width, depth, L3, t1, t2, t3, f1h, f2h, f3h, f1v, f2v, f3v, L1):
        self.width = width
        self.depth = depth
        self.L3 = L3
        
        self.t1 = t1
        self.t2 = t2
        self.t3 = t3
        
        self.f1h = f1h
        self.f2h = f2h
        self.f3h = f3h
        
        self.f1v = f1v
        self.f2v = f2v
        self.f3v = f3v
        
        self.L1 = L1
        # self.L2 = L2 Por ahora hacer la sección simetrica

    def outer_points(self):
        "Return the section's output points"
        points = np.empty([10, 2])

        points[0, 0] = self.width / 2 - (self.L1 + self.L3)
        points[0, 1] = 0
        
        points[1, 0] = self.width / 2 - self.L1
        points[1, 1] = self.depth - (self.t1 + self.f1v)
        
        points[2, 0] = self.width / 2 - (self.L1 - self.f1h)
        points[2, 1] = self.depth - self.t1
        
        points[3, 0] = self.width / 2
        points[3, 1] = self.depth - self.t1
        
        points[4, 0] = points[3, 0]
        points[4, 1] = self.depth
        
        points[5, 0] = -points[4, 0]
        points[5, 1] = points[4, 1]
        
        points[6, 0] = -points[3, 0]
        points[6, 1] = points[3, 1]
        
        points[7, 0] = -points[2, 0]
        points[7, 1] = points[2, 1]
        
        points[8, 0] = -points[1, 0]
        points[8, 1] = points[1, 1]
        
        points[9, 0] = -points[0, 0]
        points[9, 1] = points[0, 1]

        return points

    def inner_points(self):
        "Return the section's inner points"

        aux_points = np.empty([4, 2])
        points = np.empty([8, 2])
        
        # pendiente
        dx = self.L3
        dy = self.depth - (self.t1 + self.f1v)
                
        # puntos auxiliares
        c = self.t3 / ((dx ** 2 + dy ** 2) ** 0.5)
        xi = -dy * c
        yi = dx * c
        
        aux_points[0, 0] = (self.width / 2 - (self.L1 + self.L3)) + xi + (self.t2 - yi) * dx / dy
        aux_points[0, 1] = self.t2
        
        aux_points[1, 0] = aux_points[0, 0] + (self.depth - self.t1 - aux_points[0, 1]) * dx / dy
        aux_points[1, 1] = self.depth - self.t1
        
        aux_points[2, 0] = -aux_points[1, 0]
        aux_points[2, 1] = aux_points[1, 1]
        
        aux_points[3, 0] = -aux_points[0, 0]
        aux_points[3, 1] = aux_points[0, 1]
        
        # puntos externos
        points[0, 0] = aux_points[0, 0] - self.f3h
        points[0, 1] = aux_points[0, 1]
        
        points[1, 0] = aux_points[0, 0] + self.f3v * (dx / dy)
        points[1, 1] = aux_points[0, 1] + self.f3v
        
        points[2, 0] = aux_points[1, 0] - self.f2v * (dx / dy)
        points[2, 1] = aux_points[1, 1] - self.f2v
        
        points[3, 0] = points[2, 0] - self.f2h
        points[3, 1] = aux_points[1, 1]
        
        points[4, 0] = -points[3, 0]
        points[4, 1] = points[3, 1]
        
        points[5, 0] = -points[2, 0]
        points[5, 1] = points[2, 1]
        
        points[6, 0] = -points[1, 0]
        points[6, 1] = points[1, 1]
        
        points[7, 0] = -points[0, 0]
        points[7, 1] = points[0, 1]

        return points

    def plot(self, filename):
        "Draw the concrete box girder"
        
        # outer
        outer_points = self.outer_points()
        x = np.append(outer_points[:, 0], outer_points[0, 0])
        y = np.append(outer_points[:, 1], outer_points[0, 1])

        plt.plot(x, y, color='black', linewidth=1)  # borde

        y = y[[0, 1, 3, 4, 7]]
        x = x[[0, 1, 3, 4, 7]]

        plt.scatter(x, y)

        innerPoints = self.inner_points()
        x = np.append(innerPoints[:, 0], innerPoints[0, 0])
        y = np.append(innerPoints[:, 1], innerPoints[0, 1])

        plt.plot(x, y, color='black', linewidth=1)

        y = y[[4, 5, 6]]
        x = x[[4, 5, 6]]

        plt.scatter(x, y)


        for xi, yi in outer_points[[0, 4, 7], :]:
            plt.annotate('({:.2f}, {:.2f})'.format(xi, yi), (xi, yi), textcoords="offset points", xytext=(10,10), ha='left')

        for xi, yi in outer_points[[1, 3], :]:
            plt.annotate('({:.2f}, {:.2f})'.format(xi, yi), (xi, yi), textcoords="offset points", xytext=(10,-15), ha='left')
        
        for xi, yi in innerPoints[[7], :]:
            plt.annotate('({:.2f}, {:.2f})'.format(xi, yi), (xi, yi), textcoords="offset points", xytext=(10,10), ha='left')

        for xi, yi in innerPoints[[4, 5], :]:
            plt.annotate('({:.2f}, {:.2f})'.format(xi, yi), (xi, yi), textcoords="offset points", xytext=(10,-15), ha='left')

        plt.grid(True, 'both')
        plt.minorticks_on()

        ax = plt.axes()
        ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
        ax.xaxis.set_minor_locator(ticker.MultipleLocator(0.2))
        ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
        ax.yaxis.set_minor_locator(ticker.MultipleLocator(0.2))        
        
        plt.gca().set_aspect('equal', adjustable='box')

        plt.savefig(filename)
    
    def xinf(self):
        return (self.Qy(self.outer_points()) - self.Qy(self.inner_points())) / self.area()

    def yinf(self):
        return (self.Qx(self.outer_points()) - self.Qx(self.inner_points())) / self.area()

    def ysup(self):
        return self.depth - self.yinf()
    
    def area(self):
        return super().A(self.outer_points()) - super().A(self.inner_points())

    def Sxinf(self):
        return self.Ixx() / self.yinf()

    def Sxsup(self):
        return self.Ixx() / self.ysup()

    def Ixx(self):
        outer_points = self.outer_points()
        inner_points = self.inner_points()
        
        y = self.yinf()
        
        Ixx = super().Ixx(outer_points) + super().A(outer_points) * (y - super().y(outer_points)) ** 2
        Ixx-=(super().Ixx(inner_points) + super().A(inner_points) * (y - super().y(inner_points)) ** 2)
    
        return Ixx
        
    def inertia_yy(self):
        outer_points = self.outer_points()
        inner_points = self.inner_points()

        x = self.xinf()
        
        Iyy = super().Iyy(outer_points) + super().A(outer_points) * (x - super().x(outer_points)) ** 2
        Iyy-=(super().Iyy(inner_points) + super().A(inner_points) * (x - super().x(inner_points)) ** 2)

        return Iyy


class CompositeSection:
    def __init__(self, beam_section_obj, deck_section_obj, haunch_thickness):
        self.beam = beam_section_obj
        self.deck = deck_section_obj
        self.t2 = haunch_thickness
        
        self.deck_global_y_offset = self.beam.height + self.t2
        
        self._calculate_composite_properties()

    def _calculate_composite_properties(self):
        area_beam = self.beam.area
        z_beam = self.beam.z
        Iyy_beam = self.beam.Iyy

        area_t2 = self.t2 * self.beam.b1
        z_t2 = self.beam.height + self.t2 / 2
        Iyy_t2 = (1 / 12) * self.beam.b1 * self.t2 ** 3

        area_deck = self.deck.area
        z_deck_local = self.deck.z
        z_deck_global = self.deck_global_y_offset + z_deck_local
        Iyy_deck = self.deck.Iyy

        self._area_composite = (area_beam + area_t2 + area_deck)

        Qy_composite_total = (area_beam * z_beam +
                              area_deck * z_deck_global +
                              area_t2 * z_t2)
        self._zi = Qy_composite_total / self.area

        self._zs = (self.beam.height + self.t2 + self.deck.thickness) - \
            self.zi

        d_beam = self.zi - z_beam
        self._Iyy = Iyy_beam + area_beam * d_beam ** 2
        
        d_t2 = self.zi - z_t2
        self._Iyy+= Iyy_t2 + area_t2 * d_t2 ** 2

        d_deck = self.zi - z_deck_global
        self._Iyy+= Iyy_deck + area_deck * d_deck ** 2
        
    @property
    def area(self):
        return self._area_composite

    @property
    def zi(self):
        return self._zi

    @property
    def zs(self):
        return self._zs

    @property
    def Iyy(self):
        """
        Momento de inercia Ixx de la sección compuesta
        (alrededor de su propio centroide, eje horizontal).
        """
        return self._Iyy

    @property
    def wi(self):
        return self.Iyy / self.zi

    @property
    def ws(self):
        return self.Iyy / self.zs

    def plot(self, filename=None):
        plt.figure()
        
        # Dibujar la viga
        beam_pts = self.beam.points
        x = np.append(beam_pts[:, 0], beam_pts[0, 0])
        y = np.append(beam_pts[:, 1], beam_pts[0, 1])
        
        plt.plot(x, y, color='black', linewidth=1)
        plt.fill(x, y, 'lightgray', alpha=0.4)
        plt.scatter(x, y, color='red')

        # Dibujar la losa (aplicando el offset global a sus puntos locales)
        deck_pts_for_plot = self.deck.points.copy()
        deck_pts_for_plot[:, 1] += self.deck_global_y_offset
        x = np.append(deck_pts_for_plot[:, 0], deck_pts_for_plot[0, 0])
        y = np.append(deck_pts_for_plot[:, 1], deck_pts_for_plot[0, 1])        
        plt.plot(x, y, color='black', linewidth=1)
        plt.fill(x, y, 'lightgray', alpha=0.4)
        plt.scatter(x, y, color='red')

        # Dibujar centroide compuesto
        # plt.scatter(0, self.zi, color='green', zorder=5, s=100, label='Centroide Compuesto (0, Yc)')
        # plt.axhline(self.zi, color='green', linestyle='--', linewidth=0.8)

        plt.grid(True, 'both')
        plt.minorticks_on()
        ax = plt.gca()
        ax.set_aspect('equal', adjustable='box')
        ax.xaxis.set_major_locator(ticker.MultipleLocator(0.4))
        ax.yaxis.set_major_locator(ticker.MultipleLocator(0.4))
        
        if filename:
            plt.savefig(filename, bbox_inches='tight', pad_inches=0)
        else:
            plt.show()
