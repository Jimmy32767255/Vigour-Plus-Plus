import sys
import asyncio
import psutil
import sounddevice as sd
import numpy as np
from loguru import logger
from PyQt5.QtWidgets import (QApplication, QMainWindow, QSystemTrayIcon, QMenu,
                             QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QGroupBox,
                             QPushButton, QSpacerItem, QSizePolicy)
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import QTimer, QSettings, Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer, QSettings, Qt

# 配置日志
logger.add("log.log", rotation="1 MB")

class FanSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 初始化设置
        self.settings = QSettings("config.ini", QSettings.IniFormat)
        self.load_settings()
        
        # 初始化音频参数
        self.sample_rate = 44100
        self.current_freq = 100
        self.target_freq = 100
        self.current_volume = 0.1
        self.target_volume = 0.1
        self.stream = None
        self.is_running = False
        
        # 平滑过渡参数
        self.transition_speed = 0.03  # 过渡速度因子
        
        # 设置窗口属性
        self.setWindowTitle("Vigour++")
        self.setFixedSize(435, 690)
        self.setMinimumSize(435, 690)

        # 应用深色主题样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2E2E2E;
            }
            QWidget {
                background-color: #2E2E2E;
                color: #FFFFFF;
            }
            QGroupBox {
                background-color: #3C3C3C;
                border: 1px solid #555555;
                border-radius: 5px;
                margin-top: 1ex; /* 为标题留出空间 */
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 3px;
                background-color: #3C3C3C;
                color: #FFFFFF;
            }
            QLabel {
                color: #E0E0E0;
            }
            QSlider::groove:horizontal {
                border: 1px solid #555555;
                height: 8px;
                background: #555555;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #D84315; /* 橙红色滑块 */
                border: 1px solid #D84315;
                width: 18px;
                margin: -5px 0; 
                border-radius: 9px;
            }
            QPushButton {
                background-color: #4A4A4A;
                color: #FFFFFF;
                border: 1px solid #555555;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5A5A5A;
            }
            QPushButton:pressed {
                background-color: #6A6A6A;
            }
            QMenu {
                background-color: #3C3C3C;
                color: #FFFFFF;
                border: 1px solid #555555;
            }
            QMenu::item:selected {
                background-color: #5A5A5A;
            }
        """)

        # 创建主窗口部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        # 顶部标题
        title_label = QLabel("Vigour++")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("padding: 10px; background-color: #3C3C3C; border-radius: 5px;")
        self.layout.addWidget(title_label)

        # 创建频率范围控制
        freq_group = QGroupBox("频率范围")
        freq_layout = QVBoxLayout()
        self.freq_min_max_label = QLabel(f"范围: {self.min_freq}Hz - {self.max_freq}Hz") # 显示范围
        self.freq_min_max_label.setAlignment(Qt.AlignCenter)
        freq_layout.addWidget(self.freq_min_max_label)
        self.freq_slider = QSlider(Qt.Horizontal)
        self.freq_slider.setMinimum(self.min_freq)
        self.freq_slider.setMaximum(self.max_freq)
        self.freq_slider.setValue(self.current_freq)
        self.freq_slider.valueChanged.connect(self.on_freq_slider_changed) # 连接处理函数
        freq_layout.addWidget(self.freq_slider)
        freq_group.setLayout(freq_layout)
        self.layout.addWidget(freq_group)
        
        # 创建音量范围控制
        volume_group = QGroupBox("音量范围")
        volume_layout = QVBoxLayout()
        self.volume_min_max_label = QLabel(f"范围: {int(self.min_volume*100)}% - {int(self.max_volume*100)}%") # 显示范围
        self.volume_min_max_label.setAlignment(Qt.AlignCenter)
        volume_layout.addWidget(self.volume_min_max_label)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(int(self.min_volume * 100))
        self.volume_slider.setMaximum(int(self.max_volume * 100))
        self.volume_slider.setValue(int(self.current_volume * 100))
        self.volume_slider.valueChanged.connect(self.on_volume_slider_changed) # 连接到处理函数
        volume_layout.addWidget(self.volume_slider)
        volume_group.setLayout(volume_layout)
        self.layout.addWidget(volume_group)

        # Github 链接
        discord_label = QLabel("<a href='https://github.com/Jimmy32767255/Vigour-Plus-Plus' style='color: #D84315; text-decoration: none;'>Our GitHub</a>")
        discord_label.setAlignment(Qt.AlignRight)
        discord_label.setOpenExternalLinks(True)
        self.layout.addWidget(discord_label)

        # 添加一些间隔
        self.layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # 底部信息区域
        bottom_info_layout = QVBoxLayout()
        bottom_info_layout.setSpacing(5)
        
        self.layout.addLayout(bottom_info_layout)

        # “Made with by” 标签
        made_by_label = QLabel("Made with ❤ by Jimmy")
        made_by_label.setAlignment(Qt.AlignCenter)
        made_by_label.setStyleSheet("font-size: 10pt; color: #A0A0A0;")
        self.layout.addWidget(made_by_label)

        # 底部链接区域
        bottom_links_layout = QHBoxLayout()
        bottom_links_layout.setSpacing(10)

        link_style = "color: #D84315; text-decoration: none; font-size: 9pt;"
        
        # CPU负载
        self.support_label = QLabel(f"<a href='#' style='{link_style}'>CPU: {psutil.cpu_percent()}%</a>")
        self.support_label.setAlignment(Qt.AlignCenter)
        bottom_links_layout.addWidget(self.support_label)

        # 当前频率
        self.current_freq_display_label = QLabel(f"<a href='#' style='{link_style}'>频率: {int(self.current_freq)}Hz</a>")
        self.current_freq_display_label.setAlignment(Qt.AlignCenter)
        bottom_links_layout.addWidget(self.current_freq_display_label)

        # 当前音量
        self.current_volume_display_label = QLabel(f"<a href='#' style='{link_style}'>音量: {int(self.current_volume*100)}%</a>")
        self.current_volume_display_label.setAlignment(Qt.AlignCenter)
        bottom_links_layout.addWidget(self.current_volume_display_label)

        self.layout.addLayout(bottom_links_layout)

        # 版本号
        version_label = QLabel("V0.1.0R")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("font-size: 8pt; color: #808080;")
        self.layout.addWidget(version_label)

        # 控制按钮
        self.control_button = QPushButton("开始")
        self.control_button.clicked.connect(self.toggle_audio)
        self.layout.addWidget(self.control_button)

        # 添加一个伸缩项，将内容推向顶部
        self.layout.addStretch(1)
        
        # 创建系统托盘图标
        self.create_tray_icon()
        
        # 设置定时器更新CPU负载
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_cpu_load)
        self.timer.start(self.update_interval)  # 使用配置的间隔时间刷新
        
    def load_settings(self):
        """从配置文件加载设置"""
        try:
            # 从[Settings]部分加载设置
            self.min_freq = self.settings.value("Settings/min_freq", 1400, type=int)
            self.max_freq = self.settings.value("Settings/max_freq", 2500, type=int)
            self.min_volume = self.settings.value("Settings/min_volume", 0.01, type=float)
            self.max_volume = self.settings.value("Settings/max_volume", 0.5, type=float)
            self.update_interval = self.settings.value("Settings/update_interval", 100, type=int)
            
            # 从[Audio]部分加载设置
            self.sample_rate = self.settings.value("Audio/sample_rate", 44100, type=int)
            
            # 从[Window]部分加载设置
            self.hide_on_startup = self.settings.value("Window/hide_on_startup", False, type=bool)
            
            logger.success("配置文件加载成功")
        except Exception as e:
            logger.error(f"配置文件加载失败: {str(e)}")
        
    def create_tray_icon(self):
        """创建系统托盘图标和菜单"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.ico"))
        
        menu = QMenu()
        # 添加显示/隐藏窗口的选项
        toggle_action = menu.addAction("显示/隐藏窗口")
        toggle_action.triggered.connect(self.toggle_window)
        menu.addSeparator()
        # 添加开始/停止音频的选项
        self.toggle_audio_action = menu.addAction("开始模拟") # 初始文本
        self.toggle_audio_action.triggered.connect(self.toggle_audio_from_tray)
        menu.addSeparator()
        exit_action = menu.addAction("退出")
        exit_action.triggered.connect(self.close_app)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()
        
    def start_audio_stream(self):
        """启动音频流"""
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            callback=self.audio_callback,
            finished_callback=self.stream_finished
        )
        self.stream.start()
        
    def audio_callback(self, outdata, frames, time, status):
        """音频回调函数，生成声音"""
        t = np.arange(frames) / self.sample_rate
        data = np.sin(2 * np.pi * self.current_freq * t) * self.current_volume
        outdata[:] = data.reshape(-1, 1)
        
    def stream_finished(self):
        """音频流结束回调"""
        logger.info("音频流已停止")
        
    def update_cpu_load(self):
        """更新CPU负载并调整音频参数"""
        cpu_percent = psutil.cpu_percent()
        
        # 更新CPU显示
        self.support_label.setText(f"CPU使用率: {cpu_percent}%")
        
        if self.is_running:
            # 根据CPU负载计算目标频率和音量
            self.target_freq = self.min_freq + (self.max_freq - self.min_freq) * (cpu_percent / 100)
            self.target_volume = self.min_volume + (self.max_volume - self.min_volume) * (cpu_percent / 100)
            
            # 平滑过渡到目标值
            self.current_freq += (self.target_freq - self.current_freq) * self.transition_speed
            self.current_volume += (self.target_volume - self.current_volume) * self.transition_speed
            
            # 更新滑动条位置和显示值
            self.freq_slider.setValue(int(self.current_freq))
            self.freq_slider.setValue(int(self.current_freq)) # 更新滑块
        self.current_freq_display_label.setText(f"当前频率: {int(self.current_freq)}Hz") # 更新底部显示
        self.volume_slider.setValue(int(self.current_volume * 100))
        self.current_volume_display_label.setText(f"当前音量: {int(self.current_volume * 100)}%") # 更新底部显示

    def on_freq_slider_changed(self, value):
        """频率范围滑块值改变时的处理函数"""
        # 这个滑块现在控制的是 self.current_freq 的值，而不是 min_freq 或 max_freq
        # 如果希望滑块控制范围，则需要修改逻辑，例如一个滑块控制min，一个控制max
        # 或者一个滑块控制当前值，范围在配置文件中设定
        # 根据当前UI，这个滑块应该直接调整 current_freq
        self.target_freq = value
        self.current_freq = value # 手动调节时直接设置当前值
        self.current_freq_display_label.setText(f"当前频率: {value}Hz")
        # 如果需要，也可以更新 self.freq_slider.setValue(value) 但通常是自动的

    def on_volume_slider_changed(self, value):
        """音量范围滑块值改变时的处理函数"""
        volume = value / 100
        self.target_volume = volume
        self.current_volume = volume # 手动调节时直接设置当前值
        self.current_volume_display_label.setText(f"当前音量: {value}%")
        
    def toggle_audio(self):
        """切换音频状态"""
        if not self.is_running:
            self.start_audio_stream()
            self.is_running = True
        else:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            self.is_running = False
        
    def close_app(self):
        """关闭应用程序"""
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.tray_icon.hide()
        QApplication.quit()

    def toggle_window(self):
        """切换窗口的显示和隐藏状态"""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow() # 确保窗口到最前

    def toggle_audio_from_tray(self):
        """从托盘菜单切换音频状态"""
        self.toggle_audio() # 调用现有的切换逻辑
        if self.is_running:
            self.toggle_audio_action.setText("停止模拟")
        else:
            self.toggle_audio_action.setText("开始模拟")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 创建主窗口
    fan_simulator = FanSimulator()
    
    # 根据配置决定是否隐藏窗口
    if fan_simulator.hide_on_startup:
        fan_simulator.hide()
    else:
        fan_simulator.show()
    
    sys.exit(app.exec_())