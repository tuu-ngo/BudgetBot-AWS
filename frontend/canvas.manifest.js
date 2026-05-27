export const manifest = {
  screens: {
    scr_q4j8kf: { name: "Upload", route: "/", position: {"x":160,"y":5780} },
    scr_9bbss3: { name: "Dashboard", route: "/dashboard", position: {"x":160,"y":1820} },
    scr_4t99y7: { name: "Transactions", route: "/transactions", position: {"x":1560,"y":1820} },
    scr_n9ak18: { name: "Chat", route: "/assistant", position: {"x":160,"y":3800} },
  },
  sections: {
    sec_v8ag7i: { name: "Analytics workspace", x: 0, y: 1600, width: 4320, height: 1180 },
    sec_9ja4kc: { name: "AI Assistant", x: 0, y: 3580, width: 1520, height: 1180 },
    sec_po15v5: { name: "Data Import", x: 0, y: 5560, width: 1520, height: 1180 },
  },
  layers: [
    { kind: "section", id: "sec_v8ag7i", children: [
      { kind: "screen", id: "scr_9bbss3" },
      { kind: "screen", id: "scr_4t99y7" },
    ] },
    { kind: "section", id: "sec_9ja4kc", children: [
      { kind: "screen", id: "scr_n9ak18" },
    ] },
    { kind: "section", id: "sec_po15v5", children: [
      { kind: "screen", id: "scr_q4j8kf" },
    ] },
  ],
}
