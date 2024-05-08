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

import os
import re
from datetime import datetime

import lxml.html

from qgis.core import (
    Qgis,
    QgsBlockingNetworkRequest,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
    QgsRasterLayer,
)

from qgis.gui import QgsMapToolEmitPoint

from qgis.PyQt.QtCore import (
    QUrl,
    Qt,
)

from qgis.PyQt.QtGui import QColor, QIcon

from qgis.PyQt.QtNetwork import QNetworkRequest

from qgis.PyQt.QtWidgets import (
    QAction,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QMessageBox,
    QMenu,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)


class LuftbildfinderNRW:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.checkboxes = []
        self.add_metadata_layer = False
        self.canvas = self.iface.mapCanvas()
        self.pointTool = QgsMapToolEmitPoint(self.canvas)

    def initGui(self):
        self.toolbar = self.iface.addToolBar("Luftbildfinder NRW")
        self.toolbar.setObjectName("Luftbildfinder NRW")

        self.action = QAction(
            QIcon(os.path.join(self.plugin_dir, "luftbildfinder-nrw.png")),
            "&Luftbildfinder NRW",
            self.iface.mainWindow(),
        )
        self.aboutAction = QAction(
            QIcon(os.path.join(self.plugin_dir, "info_icon.png")),
            "&Über Luftbildfinder NRW",
            self.iface.mainWindow(),
        )
        self.action.triggered.connect(self.manageTool)
        self.aboutAction.triggered.connect(self.about)

        self.menu = QMenu("&Luftbildfinder NRW")
        self.menu.setIcon(
            QIcon(os.path.join(self.plugin_dir, "luftbildfinder-nrw.png"))
        )
        self.menu.addActions([self.action, self.aboutAction])

        self.iface.pluginMenu().addMenu(self.menu)
        self.toolbar.addAction(self.action)

        self.pointTool.canvasClicked.connect(self.luftbildfinderNrw)

    def unload(self):
        self.iface.removePluginMenu("&Luftbildfinder NRW", self.action)
        self.iface.removePluginMenu("&Luftbildfinder NRW", self.aboutAction)

        del self.action
        del self.toolbar

    def about(self):
        aboutString = (
            "Luftbildfinder NRW"
            + "<br>"
            + "Luftbilder für NRW finden und laden"
            + '<br>Autor: Kreis Viersen<br>Mail: <a href="mailto:open@kreis-viersen.de?subject=luftbildfinder">'
            + "open@kreis-viersen.de</a>"
        )
        QMessageBox.information(
            self.iface.mainWindow(), "Über Luftbildfinder NRW", aboutString
        )

    def luftbildfinderNrw(self, pt):
        try:
            original_pt = pt
            source_crs = self.canvas.mapSettings().destinationCrs()
            if source_crs != "EPSG:25832":
                target_crs = QgsCoordinateReferenceSystem("EPSG:25832")
                transform = QgsCoordinateTransform(
                    source_crs, target_crs, QgsProject.instance()
                )
                transformed_point = transform.transform(pt.x(), pt.y())
                pt = transformed_point

            group_name = "DOP_NRW_" + str(int(pt.x())) + "_" + str(int(pt.y()))

        except:
            pass
        finally:
            self.restore_previous_tool()

        def create_date_selection_dialog(dates):
            dialog = QDialog()
            dialog.setWindowTitle("Wähle Daten für Layer")
            layout = QVBoxLayout(dialog)

            self.checkboxes.clear()

            sortAscButton = QRadioButton("aufsteigend sortieren")
            sortDescButton = QRadioButton("absteigend sortieren")
            sortAscButton.setChecked(True)

            sortLayout = QHBoxLayout()
            sortLayout.addWidget(sortAscButton)
            sortLayout.addWidget(sortDescButton)
            layout.addLayout(sortLayout)

            checkboxLayout = QVBoxLayout()
            layout.addLayout(checkboxLayout)

            self.checkbox_states = {}

            def updateCheckboxes():
                sorted_dates = sorted(
                    dates, key=lambda x: x[0], reverse=not sortAscButton.isChecked()
                )
                current_states = {cb.text(): cb.isChecked() for cb in self.checkboxes}

                while checkboxLayout.count():
                    child = checkboxLayout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

                self.checkboxes.clear()

                for year, date, service, infolayer, layer in sorted_dates:
                    cb = QCheckBox(
                        date + "    " + service.replace("wms_nw_", ""), dialog
                    )
                    cb.setChecked(current_states.get(date, True))
                    checkboxLayout.addWidget(cb)
                    self.checkboxes.append(cb)

            sortAscButton.toggled.connect(updateCheckboxes)
            sortDescButton.toggled.connect(updateCheckboxes)

            updateCheckboxes()

            buttonBox = QDialogButtonBox(dialog)
            selectAllButton = QPushButton("alle wählen")
            deselectAllButton = QPushButton("keine wählen")
            toggleSelectionButton = QPushButton("Auswahl umkehren")

            buttonBox.addButton(selectAllButton, QDialogButtonBox.ActionRole)
            buttonBox.addButton(deselectAllButton, QDialogButtonBox.ActionRole)
            buttonBox.addButton(toggleSelectionButton, QDialogButtonBox.ActionRole)

            selectAllButton.clicked.connect(selectAll)
            deselectAllButton.clicked.connect(deselectAll)
            toggleSelectionButton.clicked.connect(toggleSelection)

            layout.addWidget(buttonBox)

            addMetadataCheckbox = QCheckBox("Metadatenlayer hinzufügen")
            addMetadataCheckbox.stateChanged.connect(updateMetadataLayer)
            addMetadataCheckbox.setChecked(False)
            layout.addWidget(addMetadataCheckbox)

            okCancelBox = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel
            )
            layout.addWidget(okCancelBox)
            okCancelBox.accepted.connect(dialog.accept)
            okCancelBox.rejected.connect(dialog.reject)

            return dialog

        def selectAll():
            for checkbox in self.checkboxes:
                checkbox.setChecked(True)

        def deselectAll():
            for checkbox in self.checkboxes:
                checkbox.setChecked(False)

        def toggleSelection():
            for checkbox in self.checkboxes:
                checkbox.setChecked(not checkbox.isChecked())

        def updateMetadataLayer(state):
            self.add_metadata_layer = state == Qt.Checked

        def selected_years():
            selected_years = [
                int(cb.text().split("-")[0]) for cb in self.checkboxes if cb.isChecked()
            ]
            ordered_dates = [
                t for year in selected_years for t in self.dates if int(t[0]) == year
            ]

            return ordered_dates

        self.dates = []

        available_services = [
            ("wms_nw_hist_dop", "nw_hist_dop_info", ""),
            ("wms_nw_dop", "nw_dop_utm_info", "nw_dop_rgb"),
            ("wms_nw_idop", "nw_idop_info", "nw_idop_rgb"),
            ("wms_nw_vdop", "nw_vdop_info", "nw_vdop_rgb"),
        ]
        for service, infolayer, layer in available_services:
            lon, lat = pt.x(), pt.y()
            buffer = 10
            minx, maxx, miny, maxy = (
                lon - buffer,
                lon + buffer,
                lat - buffer,
                lat + buffer,
            )

            params = {
                "language": "ger",
                "SERVICE": "WMS",
                "VERSION": "1.3.0",
                "REQUEST": "GetFeatureInfo",
                "BBOX": f"{minx},{miny},{maxx},{maxy}",
                "CRS": "EPSG:25832",
                "WIDTH": "101",
                "HEIGHT": "101",
                "LAYERS": infolayer,
                "STYLES": "",
                "FORMAT": "image/png",
                "QUERY_LAYERS": service,
                "INFO_FORMAT": "text/html",
                "I": "50",
                "J": "50",
                "FEATURE_COUNT": "100",
            }
            full_url = f"https://www.wms.nrw.de/geobasis/{service}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
            req = QNetworkRequest(QUrl(full_url))

            blocking_request = QgsBlockingNetworkRequest()
            try:
                result = blocking_request.get(req)
                if (
                    blocking_request.reply().attribute(
                        QNetworkRequest.HttpStatusCodeAttribute
                    )
                    != 200
                ):
                    self.iface.messageBar().pushMessage(
                        "Luftbildfinder NRW",
                        "HTTP Fehler für URL: " + full_url,
                        level=Qgis.Critical,
                        duration=30,
                    )
            except Exception as e:
                self.iface.messageBar().pushMessage(
                    "Luftbildfinder NRW",
                    "Netzwerkproblem mit: " + full_url + " Fehler: " + str(e),
                    level=Qgis.Critical,
                    duration=30,
                )

            if result == QgsBlockingNetworkRequest.ErrorCode.NoError:
                html_content = blocking_request.reply().content().data()
                tree = lxml.html.fromstring(html_content)
                date_texts = tree.xpath(
                    "//tr[contains(., 'Bildflugdatum')]/td[2]/text()"
                )
                date_regex = r"\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}"

                standardized_dates = []
                for date_text in date_texts:
                    date_text = date_text.strip()
                    if re.match(date_regex, date_text):
                        try:
                            if not"-00-00" in date_text:
                                if "-" in date_text:
                                    date_obj = datetime.strptime(date_text, "%Y-%m-%d")
                                elif "." in date_text:
                                    date_obj = datetime.strptime(date_text, "%d.%m.%Y")
                                standardized_date = datetime.strftime(date_obj, "%Y-%m-%d")
                            elif "-00-00" in date_text:
                                standardized_date = date_text
                            year = standardized_date.split("-")[0]
                            if service == "wms_nw_hist_dop":
                                layer = f"nw_hist_dop_{year}"

                            standardized_dates.append(
                                (year, standardized_date, service, infolayer, layer)
                            )
                        except:
                            pass

                if standardized_dates:
                    self.dates += standardized_dates
                else:
                    pass

            else:
                pass

        if len(self.dates) == 0:
            self.iface.messageBar().pushMessage(
                "Luftbildfinder NRW",
                "Keine Luftbilder an dieser Position gefunden",
                level=Qgis.Warning,
                duration=5,
            )
            return

        dialog = create_date_selection_dialog(self.dates)
        if dialog.exec_():
            selected_years = selected_years()
            root = QgsProject.instance().layerTreeRoot()

            suffix = 0
            for group in [child for child in root.children() if child.nodeType() == 0]:
                if (group_name) in group.name():
                    if (group_name + "_") in group.name():
                        this_suffix = group.name().split(group_name + "_", 1)[1]
                        if int(this_suffix) >= suffix:
                            suffix = int(this_suffix) + 1
                    else:
                        suffix = 1

            if suffix != 0:
                group_name = group_name + "_" + str(suffix)

            new_group = root.insertGroup(0, group_name)

            metadata_layers = []
            for year, date, service, infolayer, layer in selected_years:
                if not any(item[1] == infolayer for item in metadata_layers):
                    metadata_layers.append((service, infolayer))
                BASE_URL = f"https://www.wms.nrw.de/geobasis/{service}"
                urlWithParams = f"crs=EPSG:25832&format=image/png&layers={layer}&styles&url={BASE_URL}"
                rlayer = QgsRasterLayer(urlWithParams, f"Luftbild {layer}", "wms")
                if not rlayer.isValid():
                    pass
                else:
                    QgsProject.instance().addMapLayer(rlayer, False)
                    new_group.insertLayer(-1, rlayer)
                    rlayerNode = root.findLayer(rlayer.id())
                    rlayerNode.setExpanded(False)
                    QgsProject.instance().addMapLayer(rlayer)

                    self.canvas.flashGeometries(
                        [QgsGeometry.fromPointXY(original_pt)],
                        source_crs,
                        QColor(255, 0, 0, 255),
                        QColor(255, 0, 0, 255),
                        int(10),
                        int(500),
                    )

            if self.add_metadata_layer:
                for service, infolayer in metadata_layers:
                    BASE_URL = f"https://www.wms.nrw.de/geobasis/{service}"
                    urlWithParams = f"crs=EPSG:25832&format=image/png&layers={infolayer}&styles&url={BASE_URL}&featureCount=100"
                    rlayer = QgsRasterLayer(
                        urlWithParams, f"Metadaten {service}", "wms"
                    )
                    if not rlayer.isValid():
                        pass
                    else:
                        QgsProject.instance().addMapLayer(rlayer, False)
                        new_group.insertLayer(0, rlayer)
                        rlayerNode = root.findLayer(rlayer.id())
                        rlayerNode.setItemVisibilityChecked(False)
                        rlayerNode.setExpanded(False)
                        QgsProject.instance().addMapLayer(rlayer)

    def restore_previous_tool(self):
        if self.previousTool is not None:
            self.iface.mapCanvas().setMapTool(self.previousTool)
            self.previousTool = None

    def manageTool(self):
        if not (self.pointTool is None):
            self.pointTool.canvasClicked.disconnect()
            del self.pointTool
            self.previousTool = None
            self.pointTool = None

        canvas = self.iface.mapCanvas()
        self.previousTool = canvas.mapTool()
        self.pointTool = QgsMapToolEmitPoint(canvas)
        self.pointTool.canvasClicked.connect(self.luftbildfinderNrw)
        canvas.setMapTool(self.pointTool)
