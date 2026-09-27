-- Isolated stand-in for the reviewed typed Hyprland Lua API, never a compositor.
local callbacks, windows, operations = {}, {}, {}
local queries, recurse, fail_move, fail_resize, expire_on_move = 0, false, false, false, false
local old_monitor, new_monitor = {scale = 2}, {scale = 1}
local old_workspace, destination = {monitor = old_monitor}, {monitor = new_monitor}
local main = {mapped = true, xwayland = true, class = "steam_app_fusion360",
              initial_title = "  Autodesk Fusion  ", pid = 42, monitor = old_monitor}
local function child(overrides)
  local result = {mapped = true, xwayland = true, floating = true, class = "steam_app_fusion360",
                  initial_title = "Fusion360", pid = 42, workspace = old_workspace,
                  monitor = old_monitor, size = {x = 300, y = 200}}
  for key, value in pairs(overrides or {}) do result[key] = value end
  return result
end
local function move(args)
  return function()
    assert(args.follow == false)
    table.insert(operations, {kind = "move", args = args})
    if fail_move then return {ok = false} end
    args.window.workspace, args.window.monitor = args.workspace, args.workspace.monitor
    -- Resizing by the compositor while moving must not change the captured size.
    args.window.size = {x = 1, y = 1}
    if expire_on_move then args.window.mapped = false end
    if recurse then callbacks["window.move_to_workspace"](args.window, args.workspace) end
    return {ok = true}
  end
end
local function resize(args)
  return function()
    assert(args.relative == false)
    table.insert(operations, {kind = "resize", args = args})
    if fail_resize then return {ok = false} end
    args.window.size = {x = args.x, y = args.y}
    return {ok = true}
  end
end
local environment = {
  type = type, math = math, ipairs = ipairs,
  o = {window = function() end},
  hl = {
    on = function(name, callback)
      assert(name == "window.move_to_workspace" or name == "window.active" or name == "window.fullscreen")
      assert(not callbacks[name])
      callbacks[name] = callback
    end,
    get_windows = function(filter)
      assert(filter.class == "steam_app_fusion360" and filter.mapped == true and filter.floating == true)
      queries = queries + 1
      return windows
    end,
    dispatch = function(fn) return fn() end,
    dsp = {window = {move = move, resize = resize}},
  },
}
local original_keys = {}
for key in pairs(environment) do original_keys[key] = true end
local block = assert(io.open(arg[1], "rb")):read("*a")
assert(load(block, "owned Fusion block", "t", environment))()
assert(callbacks["window.move_to_workspace"] and callbacks["window.active"] and callbacks["window.fullscreen"])
assert(queries == 0 and #operations == 0)
for key in pairs(environment) do assert(original_keys[key], "hook leaked a global: " .. key) end
local callback = callbacks["window.move_to_workspace"]
-- Per-test assertions follow in the same lexical scope.
