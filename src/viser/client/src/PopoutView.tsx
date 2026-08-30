// The pop-out view (Dexory fork): a client loaded with `?panel=<key>` renders
// exactly one standalone panel (`gui.add_panel(key=...)`) full-window -- no
// canvas, no dock, no control panel. It is an ordinary viser client in every
// other way: the same websocket producer feeds the same stores, so GUI state
// and interactions stay in sync with every other window for free (server-owned
// GUI is the whole mechanism; a pop-out is just a late joiner that declines to
// render the rest).
//
// Because the frame-synchronized message pump lives inside the R3F canvas
// (which this view never mounts), PopoutMessagePump drains the queue itself on
// an interval. Scene messages still populate the scene stores (unrendered) --
// memory proportional to the scene, deliberately accepted for v1 over
// maintaining a message-type whitelist that would drift. Server render
// requests cannot be fulfilled here (no GL); they are handled (state set) and
// simply never answered, matching a client whose canvas never produces frames.

import {
  Box,
  Center,
  MantineProvider,
  Tabs,
  Text,
  createTheme,
  useMantineColorScheme,
  v8CssVariablesResolver,
} from "@mantine/core";
import React, { useContext, useEffect, useMemo } from "react";
import { ViewerContext } from "./ViewerContext";
import { theme } from "./AppTheme";
import { htmlIconWrapper } from "./components/ComponentStyles.css";
import GeneratedGuiContainer from "./ControlPanel/Generated";
import { applyGuiUpdatesBatch, useMessageHandler } from "./MessageHandler";

/** The server only registers a ClientHandle -- and only then dispatches GUI
 * callbacks for this client's updates -- "after the first camera message is
 * received" (_viser.py). A canvas-less client never sends one naturally, and
 * the failure is deceptive: value updates still broadcast to other clients
 * while every on_click/on_update is silently skipped (found live, 2026-08-30).
 * Send one honest nominal camera per connection instead. */
function PopoutClientRegistration() {
  const viewer = useContext(ViewerContext)!;
  const websocketState = viewer.useGui((state) => state.websocketState);
  useEffect(() => {
    if (websocketState !== "connected") return;
    viewer.mutable.current.sendMessage({
      type: "ViewerCameraMessage",
      wxyz: [1, 0, 0, 0],
      position: [0, 0, 0],
      fov: 1.0,
      near: 0.1,
      far: 1000.0,
      image_height: 1,
      image_width: 1,
      look_at: [0, 0, 0],
      up_direction: [0, 0, 1],
    });
  }, [websocketState, viewer]);
  return null;
}

/** Drains the websocket message queue outside any R3F canvas. */
function PopoutMessagePump() {
  const handleMessage = useMessageHandler();
  const viewer = useContext(ViewerContext)!;
  useEffect(() => {
    const interval = setInterval(() => {
      // Read the queue REFERENCE fresh each tick: the producer may swap the
      // array on (re)connect, and a captured stale array would silently
      // starve this pump of every post-swap message.
      const queue = viewer.mutable.current.messageQueue;
      if (queue.length === 0) return;
      // `handleMessage` applies structural changes itself but RETURNS value
      // updates as batch descriptors (the frame pump applies them as single
      // setState calls). Collect and apply the GUI ones the same shared way;
      // scene attr/props descriptors are deliberately dropped -- nothing here
      // renders the scene, and parking machinery assumes the canvas world.
      const guiUpdates: { uuid: string; updates: { [key: string]: any } }[] =
        [];
      while (queue.length > 0) {
        const message = queue.shift()!;
        try {
          const result = handleMessage(message);
          if (result?.kind === "guiUpdate") guiUpdates.push(result);
        } catch (error) {
          // A canvas-less client: scene-side handlers may assume objects the
          // Canvas would have created. One bad message must never stall the
          // pump (GUI messages behind it still matter).
          console.warn(
            `popout: dropped ${message.type} (handler threw)`,
            error,
          );
        }
      }
      applyGuiUpdatesBatch(viewer, guiUpdates);
    }, 30);
    return () => clearInterval(interval);
  }, [handleMessage, viewer]);
  return null;
}

function PopoutPanelBody({ panelKey }: { panelKey: string }) {
  const viewer = useContext(ViewerContext)!;
  const panels = viewer.useGui((state) => state.panels);
  const panel = useMemo(
    () =>
      Object.values(panels).find(
        (candidate) => candidate.props.key === panelKey,
      ),
    [panels, panelKey],
  );

  useEffect(() => {
    document.title = panel === undefined ? "viser" : `${panelKey} — viser`;
  }, [panel, panelKey]);

  const [activeTab, setActiveTab] = React.useState<string | null>(null);

  if (panel === undefined) {
    // Covers both "still connecting/replaying" and "no such key" honestly:
    // the panel appears the moment the server sends it; if it never does,
    // this note is the truth.
    return (
      <Center style={{ height: "100%" }}>
        <Text c="dimmed" size="sm" data-popout-waiting={panelKey}>
          waiting for a panel with key &lsquo;{panelKey}&rsquo; from this
          server&hellip;
        </Text>
      </Center>
    );
  }

  const ids = panel.props._tab_container_ids;
  const labels = panel.props._tab_labels;
  const icons = panel.props._tab_icons_html;
  const active =
    activeTab !== null && ids.includes(activeTab) ? activeTab : ids[0];

  return (
    <Tabs
      value={active ?? null}
      onChange={setActiveTab}
      keepMounted
      style={{ height: "100%", display: "flex", flexDirection: "column" }}
      data-popout-panel={panelKey}
    >
      <Tabs.List>
        {ids.map((cid, i) => (
          <Tabs.Tab
            key={cid}
            value={cid}
            leftSection={
              icons[i] == null ? undefined : (
                <div
                  className={htmlIconWrapper}
                  dangerouslySetInnerHTML={{ __html: icons[i]! }}
                />
              )
            }
          >
            {labels[i] ?? "Tab"}
          </Tabs.Tab>
        ))}
      </Tabs.List>
      {ids.map((cid) => (
        <Tabs.Panel
          key={cid}
          value={cid}
          style={{ flexGrow: 1, minHeight: 0, overflowY: "auto" }}
        >
          <GeneratedGuiContainer containerUuid={cid} />
        </Tabs.Panel>
      ))}
    </Tabs>
  );
}

function PopoutColorSchemeSetter({ darkMode }: { darkMode: boolean }) {
  const colorScheme = useMantineColorScheme();
  useEffect(() => {
    colorScheme.setColorScheme(darkMode ? "dark" : "light");
  }, [darkMode]);
  return null;
}

/** The pop-out shell: Mantine chrome (server theme respected, like the main
 * view) around the one panel, plus the message pump. `children` is the
 * websocket producer -- it renders no UI but must mount for the connection to
 * exist, same as in ViewerContents. */
export function PopoutContents({
  panelKey,
  forceDarkMode,
  children,
}: {
  panelKey: string;
  forceDarkMode: boolean;
  children: React.ReactNode;
}) {
  const viewer = useContext(ViewerContext)!;
  const storeDarkMode = viewer.useGui((state) => state.theme.dark_mode);
  const colors = viewer.useGui((state) => state.theme.colors);
  const darkMode = forceDarkMode || storeDarkMode;
  const mantineTheme = useMemo(
    () =>
      createTheme({
        ...theme,
        ...(colors === null
          ? {}
          : { colors: { custom: colors }, primaryColor: "custom" }),
      }),
    [colors],
  );
  return (
    <MantineProvider
      theme={mantineTheme}
      cssVariablesResolver={v8CssVariablesResolver}
      defaultColorScheme={darkMode ? "dark" : "light"}
      colorSchemeManager={{
        get: (defaultValue) => defaultValue,
        set: () => null,
        subscribe: () => null,
        unsubscribe: () => null,
        clear: () => null,
      }}
    >
      <PopoutColorSchemeSetter darkMode={darkMode} />
      <PopoutClientRegistration />
      <PopoutMessagePump />
      <Box
        style={{
          width: "100%",
          height: "100%",
          backgroundColor: "var(--mantine-color-body)",
        }}
      >
        <PopoutPanelBody panelKey={panelKey} />
      </Box>
      {children}
    </MantineProvider>
  );
}
