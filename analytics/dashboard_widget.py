# analytics/dashboard_widget.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox,
    QSplitter
)
from PyQt6.QtCharts import (
    QChart, QChartView,
    QBarSeries, QBarSet,
    QBarCategoryAxis, QValueAxis
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QCursor
from PyQt6.QtWidgets import QToolTip

import pandas as pd

from .parser import load_results


class AnalyticsDashboard(QWidget):

    def __init__(self, output_folder: str):
        super().__init__()

        self.output_folder = output_folder
        self.df = pd.DataFrame()

        main_layout = QVBoxLayout(self)

        # ----------------------
        # Top Controls
        # ----------------------
        controls_layout = QHBoxLayout()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_data)

        self.language_selector = QComboBox()
        self.language_selector.currentIndexChanged.connect(self.update_issue_chart)

        controls_layout.addWidget(QLabel("Language:"))
        controls_layout.addWidget(self.language_selector)
        controls_layout.addStretch()
        controls_layout.addWidget(self.refresh_button)

        main_layout.addLayout(controls_layout)

        # ----------------------
        # Resizable Charts Area
        # ----------------------
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        self.issue_chart_view = QChartView()
        self.issue_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.record_chart_view = QChartView()
        self.record_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.splitter.addWidget(self.issue_chart_view)
        self.splitter.addWidget(self.record_chart_view)

        self.splitter.setSizes([400, 300])  # initial sizes

        main_layout.addWidget(self.splitter)

        self.refresh_data()

    # =====================================================
    # DATA LOADING
    # =====================================================
    def refresh_data(self):
        self.df = load_results(self.output_folder)

        self.language_selector.blockSignals(True)
        self.language_selector.clear()

        if self.df.empty:
            return

        languages = sorted(self.df["language"].dropna().unique())
        self.language_selector.addItem("All")
        self.language_selector.addItems(languages)

        self.language_selector.blockSignals(False)

        self.update_issue_chart()
        self.build_record_distribution_chart()

    # =====================================================
    # ISSUE DISTRIBUTION (WITH LANGUAGE FILTER)
    # =====================================================
    def update_issue_chart(self):

        if self.df.empty:
            return

        selected_language = self.language_selector.currentText()

        df_filtered = self.df[self.df["issue_literal"].notna()]

        if selected_language != "All":
            df_filtered = df_filtered[
                df_filtered["language"] == selected_language
            ]

        issue_df = (
            df_filtered.groupby(["issue_literal"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )

        chart = QChart()
        chart.setTitle("Issue Distribution")

        if issue_df.empty:
            self.issue_chart_view.setChart(chart)
            return

        series = QBarSeries()
        bar_set = QBarSet("Detections")

        categories = issue_df["issue_literal"].tolist()
        counts = issue_df["count"].tolist()

        bar_set.append(counts)

        bar_set.hovered.connect(
            lambda status, index, bs=bar_set, cats=categories:
                self.show_issue_tooltip(status, index, bs, cats)
        )

        series.append(bar_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsAngle(-45)

        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setTitleText("Detections")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        chart.legend().setVisible(False)

        self.issue_chart_view.setChart(chart)

    # =====================================================
    # RECORD DISTRIBUTION
    # =====================================================
    def build_record_distribution_chart(self):

        chart = QChart()
        chart.setTitle("Distribution of Issue Count per Record")

        if self.df.empty:
            self.record_chart_view.setChart(chart)
            return

        record_counts = (
            self.df.groupby("record_literal")["tag_count_per_record"]
            .max()
        )

        distribution = record_counts.value_counts().sort_index()

        series = QBarSeries()
        bar_set = QBarSet("Records")

        categories = [str(k) for k in distribution.index]
        values = distribution.values.tolist()

        bar_set.append(values)

        bar_set.hovered.connect(
            lambda status, index, bs=bar_set, cats=categories:
                self.show_record_tooltip(status, index, bs, cats)
        )

        series.append(bar_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setTitleText("Number of Issues in Record")

        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setTitleText("Number of Records")

        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        chart.legend().setVisible(False)

        self.record_chart_view.setChart(chart)

    # =====================================================
    # TOOLTIPS
    # =====================================================
    def show_issue_tooltip(self, status, index, bar_set, categories):
        if not status:
            QToolTip.hideText()
            return

        issue_literal = categories[index]
        count = int(bar_set.at(index))

        selected_language = self.language_selector.currentText()

        text = (
            f"Language: {selected_language}\n"
            f"Issue: {issue_literal}\n"
            f"Detections: {count}"
        )

        QToolTip.showText(QCursor.pos(), text)

    def show_record_tooltip(self, status, index, bar_set, categories):
        if not status:
            QToolTip.hideText()
            return

        issue_count = categories[index]
        record_count = int(bar_set.at(index))

        text = (
            f"Issues in record: {issue_count}\n"
            f"Number of records: {record_count}"
        )

        QToolTip.showText(QCursor.pos(), text)