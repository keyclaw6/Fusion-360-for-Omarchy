-- Run the owned block against typed-window stand-ins, never the live compositor.
local callbacks, operations, queries = {}, {}, 0
local workspace, other_workspace = {}, {}
local main = {mapped = true, xwayland = true, class = "steam_app_fusion360", pid = 42,
              initial_title = "  Autodesk Fusion  ", workspace = workspace, allowed_over_fullscreen = false}
local function child(overrides)
  local result = {mapped = true, xwayland = true, floating = true, class = "steam_app_fusion360", pid = 42,
                  initial_title = "Fusion360", workspace = workspace, allowed_over_fullscreen = false}
  for key, value in pairs(overrides or {}) do result[key] = value end
  return result
end
local browser, comments = child(), child()
local windows, active = {main, browser, comments}, main
local recurse, fail_raise, throw_raise, switch_active = false, false, false, nil
local environment = {
  type = type, math = math, ipairs = ipairs, pcall = pcall, error = error,
  o = {window = function() end},
  hl = {
    on = function(name, callback)
      assert(name == "window.move_to_workspace" or name == "window.active" or name == "window.fullscreen")
      assert(not callbacks[name])
      callbacks[name] = callback
    end,
    get_windows = function(filter)
      assert(filter.class == "steam_app_fusion360" and filter.mapped == true and filter.floating == nil)
      queries = queries + 1
      return windows
    end,
    get_active_window = function() return active end,
    dispatch = function(fn) return fn() end,
    dsp = {window = {alter_zorder = function(args)
      assert(args.mode == "top")
      return function()
        table.insert(operations, args.window)
        if throw_raise then error("simulated Lua dispatch failure") end
        if fail_raise then return {ok = false} end
        args.window.allowed_over_fullscreen = true
        if switch_active then active = switch_active end
        if recurse then
          callbacks["window.active"](active)
          callbacks["window.fullscreen"](main)
        end
        return {ok = true}
      end
    end}},
  },
}
local original_keys = {}
for key in pairs(environment) do original_keys[key] = true end
local file = assert(io.open(arg[1], "rb"))
local block = file:read("*a")
file:close()
assert(load(block, "owned Fusion block", "t", environment))()
assert(callbacks["window.move_to_workspace"] and callbacks["window.active"] and callbacks["window.fullscreen"])
assert(queries == 0 and #operations == 0)
for key in pairs(environment) do assert(original_keys[key], "hook leaked a global: " .. key) end
local on_active, on_fullscreen = callbacks["window.active"], callbacks["window.fullscreen"]
-- Per-test assertions follow in the same lexical scope.
