-- Exercise real Lua hooks against typed objects without touching a desktop.
local callbacks, subscriptions, operations = {}, {}, {}
local old_monitor, new_monitor = {scale=2}, {scale=1}
local old_workspace, destination = {monitor=old_monitor}, {monitor=new_monitor}
local main = {mapped=true,xwayland=true,class="steam_app_fusion360",pid=42,
  initial_title=" Autodesk Fusion ",workspace=old_workspace,monitor=old_monitor}
local function child(overrides)
  local w = {mapped=true,xwayland=true,floating=true,class="steam_app_fusion360",pid=42,
    initial_title="Fusion360",workspace=old_workspace,monitor=old_monitor,size={x=300,y=200}}
  for k,v in pairs(overrides or {}) do w[k]=v end
  return w
end
local browser, comments = child(), child()
local tray = child({initial_title="Msg:QTView:(102)MessageTray"})
local unrelated = child({class="editor"})
local windows = {main,browser,comments,tray,unrelated}
local fail_move, throw_move, recurse = false,false,true
local environment = {
  type=type,math=math,ipairs=ipairs,pcall=pcall,error=error,
  o={window=function() end},
  hl={
    on=function(name,fn)
      subscriptions[name]=subscriptions[name] or {}
      table.insert(subscriptions[name],fn)
      callbacks[name]=function(...)
        for _,handler in ipairs(subscriptions[name]) do handler(...) end
      end
    end,
    timer=function(fn,args)
      assert(args.timeout==600 and args.type=="oneshot")
      return {set_enabled=function() end}
    end,
    get_windows=function(filter)
      assert(filter.class=="steam_app_fusion360" and filter.mapped==true)
      return windows
    end,
    get_active_window=function() return nil end,
    dispatch=function(fn) return fn() end,
    dsp={window={
      move=function(args) return function()
        assert(args.follow==false)
        if throw_move then error("simulated dispatcher exception") end
        table.insert(operations,{kind="move",args=args})
        if fail_move then return {ok=false} end
        if recurse then callbacks["window.move_to_workspace"](args.window,args.workspace) end
        args.window.workspace,args.window.monitor=args.workspace,args.workspace.monitor
        args.window.size={x=1,y=1}
        return {ok=true}
      end end,
      resize=function(args) return function()
        assert(args.relative==false)
        table.insert(operations,{kind="resize",args=args})
        args.window.size={x=args.x,y=args.y}
        return {ok=true}
      end end,
    }},
  },
}
local block=assert(io.open(arg[1],"rb")):read("*a")
assert(load(block,"Fusion workspace hooks","t",environment))()
assert(callbacks["window.open"] and callbacks["window.move_to_workspace"])
assert(#operations==0)
local move, open = callbacks["window.move_to_workspace"],callbacks["window.open"]
