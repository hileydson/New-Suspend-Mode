import React, { FC } from "react";
import { PanelSection, PanelSectionRow, ToggleField, SliderField, Field } from "@decky/ui";
import { PluginSettings } from "../types";

interface AdvancedSettingsProps {
  settings: PluginSettings;
  updateSetting: <K extends keyof PluginSettings>(key: K, val: PluginSettings[K]) => void;
}

/** The sections revealed by "Advanced Features". */
export const AdvancedSettings: FC<AdvancedSettingsProps> = ({ settings, updateSetting }) => (
  <>
      {/* Behavior (advanced) */}
      <PanelSection title="Behavior">
        <PanelSectionRow>
          <ToggleField
            label="Pause Running Games"
            description="Pauses games launched through Steam before entering New Suspend Mode and resumes them after hardware and controls are restored. Online sessions may disconnect. Turn off if a game has trouble resuming."
            checked={settings.pause_running_games !== false}
            onChange={(checked) => updateSetting("pause_running_games", checked)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <SliderField
            label="Auto-Suspend Battery Threshold"
            description="Console suspends automatically if battery drops below this limit during download."
            value={settings.min_battery_threshold}
            min={5}
            max={30}
            step={1}
            showValue
            valueSuffix="%"
            onChange={(val) => updateSetting("min_battery_threshold", val)}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <SliderField
            label="HUD Display Countdown"
            description="Seconds the download card shows on screen before turning display off."
            value={settings.hud_timeout_seconds}
            min={0}
            max={15}
            step={1}
            showValue
            valueSuffix="s"
            onChange={(val) => updateSetting("hud_timeout_seconds", val)}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <SliderField
            label="Completion Suspend Delay"
            description="Seconds to wait after all downloads complete before automatically sleeping."
            value={settings.auto_suspend_delay_seconds}
            min={30}
            max={600}
            step={30}
            showValue
            valueSuffix="s"
            onChange={(val) => updateSetting("auto_suspend_delay_seconds", val)}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label="Block All Input While Screen Is Off"
            description="Freezes button mapping and disconnects external controllers so only the power button responds. Turn off if a controller misbehaves after waking."
            checked={settings.deep_input_lockout}
            onChange={(checked) => updateSetting("deep_input_lockout", checked)}
          />
        </PanelSectionRow>
      </PanelSection>

      {/* Power & screen (advanced) */}
      <PanelSection title="Power Saving & Screen Options">
        <PanelSectionRow>
          <ToggleField
            label="Turn Off Display Backlight"
            description="Physically drops LCD/OLED panel backlight brightness to 0."
            checked={settings.turn_off_backlight}
            onChange={(checked) => updateSetting("turn_off_backlight", checked)}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label="Pitch Black OLED Mode"
            description="Presents a pure black overlay, shutting off individual OLED pixels."
            checked={settings.oled_black_screen}
            onChange={(checked) => updateSetting("oled_black_screen", checked)}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label="Force TV Off (real no-signal)"
            description="Desktop with a TV only. A black screen is still a valid HDMI signal, so the TV stays lit. This stops the video signal entirely by disabling the HDMI/DP connector, so the TV reports no signal and reaches its own standby. The built-in panel of a handheld is never touched. EXPERIMENTAL: on a single-display desktop the session becomes headless while in the mode — the same as unplugging the cable — so test it before relying on it."
            checked={settings.tv_force_connector_off === true}
            onChange={(checked) => updateSetting("tv_force_connector_off", checked)}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label="Throttle CPU to Powersave"
            description="Switches power profile to power-saver and lowers CPU clock frequencies."
            checked={settings.throttle_cpu}
            onChange={(checked) => updateSetting("throttle_cpu", checked)}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label="Throttle GPU to 200MHz"
            description="Sets AMD GPU performance level to low, minimizing GPU power draw."
            checked={settings.throttle_gpu}
            onChange={(checked) => updateSetting("throttle_gpu", checked)}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label="Mute Audio While Screen Off"
            description="Silences audio output during background download to prevent disturbance."
            checked={settings.mute_audio}
            onChange={(checked) => updateSetting("mute_audio", checked)}
          />
        </PanelSectionRow>
      </PanelSection>

      {/* Standby wake sources (advanced) */}
      <PanelSection title="Standby Wake Sources">
        <PanelSectionRow>
          <Field
            label="What You Will See"
            description={
              settings.standby_on_power_off
                ? "Downloading: the download card, then black. Nothing downloading: just the plugin logo, then black."
                : "Standby off: sleep is intercepted only while a download is active, and the download card is shown."
            }
          />
        </PanelSectionRow>

        {settings.standby_on_power_off && (
          <>
            <PanelSectionRow>
              <ToggleField
                label="Wake When A Bluetooth Pad Connects"
                description="Bluetooth stays on in standby. Turning a paired controller on is enough to wake the console, no button needed."
                checked={settings.wake_on_bluetooth_connect}
                onChange={(checked) => updateSetting("wake_on_bluetooth_connect", checked)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <ToggleField
                label="Wake On Controller Button"
                description="For USB and dongle controllers, connecting is not enough: press Guide/Home, Select or Start to wake. The console's own buttons stay dead - only power works there."
                checked={settings.wake_on_controller_button}
                onChange={(checked) => updateSetting("wake_on_controller_button", checked)}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <Field
                label="Battery In Standby"
                description={`Standby keeps the console powered, so it does use battery. It drops to a real suspend at ${settings.min_battery_threshold}% to protect it.`}
              />
            </PanelSectionRow>
          </>
        )}
      </PanelSection>

      {/* Download pace (advanced) */}
      <PanelSection title="Download Pace (Fan & Heat)">
        {settings.limit_download_speed && (
          <PanelSectionRow>
            <SliderField
              label="Download Speed Cap"
              description="Lower is quieter and cooler. 6 MB/s still downloads about 21 GB per hour."
              value={settings.download_speed_limit_mbps}
              min={1}
              max={30}
              step={1}
              showValue
              valueSuffix=" MB/s"
              onChange={(val) => updateSetting("download_speed_limit_mbps", val)}
            />
          </PanelSectionRow>
        )}

        <PanelSectionRow>
          <SliderField
            label="Steam CPU Budget"
            description="Hard limit on the CPU Steam may use while the screen is off, as a share of one core. This is what keeps the chip cool enough for the fans to idle."
            value={settings.download_cpu_percent}
            min={0}
            max={100}
            step={5}
            showValue
            valueSuffix="%"
            onChange={(val) => updateSetting("download_cpu_percent", val)}
          />
        </PanelSectionRow>
      </PanelSection>

      {/* Troubleshooting (advanced) */}
      <PanelSection title="Troubleshooting">
        <PanelSectionRow>
          <ToggleField
            label="Also Disconnect Built-In Controller"
            description="EXPERIMENTAL. Only enable if buttons still act while the screen is off. Detaches the built-in pad's raw HID interface, which crashed the session on some consoles."
            checked={settings.block_controller_hidraw}
            onChange={(checked) => updateSetting("block_controller_hidraw", checked)}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label="Auto Restore Hardware After Wake"
            description="Three seconds after waking, while the wake presentation is still on screen, runs the same hard reset the button above does so clocks, turbo, ryzenadj and platform profile come back ready. Turn off if another tool manages your TDP and you prefer the button."
            checked={settings.auto_hard_reset_after_wake !== false}
            onChange={(checked) => updateSetting("auto_hard_reset_after_wake", checked)}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label="Write Diagnostic Logs"
            description="Records the full input and thermal picture to the plugin log on every screen-off. Leave on while tuning."
            checked={settings.debug_logging}
            onChange={(checked) => updateSetting("debug_logging", checked)}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <Field
            label="Restore Hardware Now — When to use it"
            description="The button above puts every clock, power limit and speed cap back without rebooting, even ones left behind by a crash. It also re-enables turbo boost, makes the firmware re-apply the current power profile, and raises any CPU ceiling still below what the chip reports — so it will overrule another tool's TDP settings while it runs."
            bottomSeparator="none"
          />
        </PanelSectionRow>
      </PanelSection>
  </>
);
