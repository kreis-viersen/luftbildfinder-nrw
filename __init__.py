"""
***************************************************************************
Luftbildfinder NRW
QGIS plugin

        Begin                : April 2024
        Copyright            : (C) Kreis Viersen
        Email                : open@kreis-viersen.de

***************************************************************************

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 3 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""


def classFactory(iface):
    from .luftbildfinder_nrw import LuftbildfinderNRW

    return LuftbildfinderNRW(iface)
