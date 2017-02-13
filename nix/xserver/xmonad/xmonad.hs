import XMonad hiding (Tall)
import XMonad.Actions.CycleWS
import XMonad.Util.EZConfig
import XMonad.Hooks.DynamicLog
import XMonad.Hooks.ManageDocks
import XMonad.Hooks.UrgencyHook
import XMonad.Layout.LayoutHints
import XMonad.Layout.HintedTile
import XMonad.Layout.ResizableTile
import XMonad.Layout.LayoutHints
import XMonad.Layout.PerWorkspace
import XMonad.ManageHook
import XMonad.Layout.Dishes
import XMonad.Layout.Grid
import XMonad.Layout.Tabbed
import XMonad.Layout.NoBorders
import XMonad.Layout.WindowNavigation
import XMonad.Prompt
import XMonad.Prompt.Shell
import XMonad.Util.Run
import Graphics.X11
import System.Exit
import System.IO
import XMonad.Hooks.ManageHelpers
import Graphics.X11.ExtraTypes.XF86
import XMonad.Actions.Volume
import XMonad.Util.Dzen
import Data.Monoid (mappend)
import Data.Map (fromList)
import XMonad.Hooks.SetWMName
import XMonad.Hooks.EwmhDesktops

 
import qualified Data.Map as M
import qualified XMonad.Actions.FlexibleResize as Flex
import qualified XMonad.StackSet as W
 
myModMask = mod4Mask

main = do
    dzen <- spawnPipe myStatusBar
    dzentop <- spawn myTopBar
    dzenbottom <- spawn myBottomBar
    xmonad $ myUrgencyHook $ ewmh $ defaultConfig
 
       { terminal = "uxterm"
       , borderWidth = 1
       , modMask = myModMask
       , focusFollowsMouse = True
       , mouseBindings = myMouseBindings
       , normalBorderColor = "#dddddd"
       , focusedBorderColor = "#0077cc"
       , layoutHook = myLayout
       , logHook = dynamicLogWithPP $ myDzenPP dzen
       , manageHook = myManageHook <+> manageDocks 
       , workspaces = ["1:main", "2:www", "3:mail", "4:chat", "5:code"] ++ map show [6..9]
       , startupHook = setWMName "LG3D"
       }
       `additionalKeys` myKeys
 
-- Statusbar options:
myStatusBar = "dzen2 -x '0' -y '0' -h '16' -w '1100' -ta 'l' -fg '#f0f0f0' -bg '#0f0f0f' -fn '-*-terminus-*-r-normal-*-*-120-*-*-*-*-iso8859-*'"

myTopBar = "conky -c /home/data/.conkytoprc | dzen2 -x '1100' -y '0' -h '16' -w '700' -ta 'r' -fg '#555555' -bg '#0f0f0f' -fn '-*-terminus-*-r-normal-*-*-120-*-*-*-*-iso8859-*'"

myBottomBar = "conky -c /home/data/.conkybottomrc | dzen2 -x '0' -y '1064' -h '16' -w '1920' -ta 'l' -fg '#555555' -bg '#0f0f0f' -fn '-*-terminus-*-r-normal-*-*-120-*-*-*-*-iso8859-*'"
 
-- Urgency hint options:
myUrgencyHook = withUrgencyHook dzenUrgencyHook
    { args = ["-x", "0", "-y", "1064", "-h", "16", "-w", "1920", "-ta", "r", "-expand", "l", "-fg", "#0099ff", "-bg", "#0f0f0f", "-fn", "-*-terminus-*-r-normal-*-*-120-*-*-*-*-iso8859-*"] }

-- Layout options:
myLayout = avoidStruts  (hintedTile Wide ||| Full ||| hintedTile Tall)
    where
        hintedTile = HintedTile nmaster delta ratio TopLeft
        resizableTile = ResizableTall nmaster delta ratio []
        nmaster = 1
        ratio = toRational (2/(1+sqrt(5)::Double)) -- Golden ratio
        delta = 3/100
 
-- XPConfig options:
myXPConfig = defaultXPConfig
    { bgColor = "#222222"
    , fgColor = "#ffffff"
    , fgHLight = "#ffffff"
    , bgHLight = "#0066ff"
    , borderColor = "#ffffff"
    , promptBorderWidth = 1
    , position = Bottom
    , height = 16
    , historySize = 100
    }
 
-- Key bindings:
	
myKeys  =
    [
        ((myModMask .|. shiftMask, xK_d        ), spawn "date | dzen2 -p 2 -xs 1") 
        , ((controlMask .|. shiftMask, xK_l), spawn "slock") -- locks screen and blacks it out
        , ((controlMask .|. shiftMask, xK_p), spawn "sudo pm-suspend") -- suspend 
        , ((myModMask .|. controlMask, xK_q), spawn "killall conky dzen2" >> restart "xmonad" True) -- restart xmonad
        , ((noModMask, xF86XK_MonBrightnessUp), spawn "xbacklight +9")
        , ((noModMask, xF86XK_MonBrightnessDown), spawn "xbacklight -9")
        , ((noModMask, xF86XK_AudioLowerVolume), lowerVolume 3 >> return())
        , ((noModMask, xF86XK_AudioRaiseVolume), raiseVolume 3 >> return())
        , ((noModMask, xF86XK_AudioMute), toggleMuteChannels ["Master", "Headphone", "Speaker"] >> return())
    ]

-- Mouse bindings:
myMouseBindings (XConfig {XMonad.modMask = modMask}) = M.fromList $
    [ ((modMask, button1), (\w -> focus w >> mouseMoveWindow w)) -- set the window to floating mode and move by dragging
    , ((modMask, button2), (\w -> focus w >> windows W.swapMaster)) -- raise the window to the top of the stack
    , ((modMask, button3), (\w -> focus w >> Flex.mouseResizeWindow w)) -- set the window to floating mode and resize by dragging
    , ((modMask, button4), (\_ -> prevWS)) -- switch to previous workspace
    , ((modMask, button5), (\_ -> nextWS)) -- switch to next workspace
    ]
 
-- Window rules:
myManageHook = composeAll . concat $
    [ [className =? c --> doFloat | c <- myFloats]
    , [title =? t --> doFloat | t <- myOtherFloats]
    , [resource =? r --> doFloat | r <- myIgnores]
    , [className =? "Firefox" --> doF (W.shift "2:www")]
    , [className =? "chromium-browser" --> doF (W.shift "2:www")]
    , [className =? "Thunderbird" --> doF (W.shift "3:mail")]
    , [className =? "Skype" --> doF (W.shift "4:chat")]
    , [resource =? "Pidgin" --> doF (W.shift "4:chat")]
    , [ composeOne [isFullscreen -?> doFullFloat] ]
    ]
    where
    myFloats = ["Ekiga", "Gimp", "gimp", "MPlayer", "Nitrogen", "Nvidia-settings", "Xmessage", "xmms"]
    myOtherFloats = ["Downloads", "Iceweasel Preferences", "Save As...", "VLC media player", "VLC (XVideo output)", "Battle.net Setup"]
    myIgnores = ["Wine"]
 
-- dynamicLog pretty printer for dzen:
myDzenPP h = defaultPP
    { 
    ppCurrent = wrap "^fg(#0099ff)^bg(#aa6b00)^p()^fg(#ffffff)" "^fg()^bg()^p()" . pad . \wsId -> if (':' `elem` wsId) then drop 2 wsId else wsId 
    , ppVisible = wrap "^fg(#ffffff)^bg(#333333)^p()^fg(#ffffff)" "^fg()^bg()^p()" . pad . \wsId -> if (':' `elem` wsId) then drop 2 wsId else wsId
    , ppHidden = wrap "" "^fg()^bg()^p()" . pad . \wsId -> if (':' `elem` wsId) then drop 2 wsId else wsId -- don't use ^fg() here!!
    , ppHiddenNoWindows = wrap "^fg(#777777)^bg()^p()" "^fg()^bg()^p()" . pad . \wsId -> if (':' `elem` wsId) then drop 2 wsId else wsId
    , ppUrgent = wrap "^fg(#0099ff)^bg()^p()" "^fg()^bg()^p()" . \wsId -> if (':' `elem` wsId) then drop 2 wsId else wsId
    , ppWsSep    = dzenColor "#bbbbbb" "#cccccc" "^r(1x18)"
    , ppSep      = dzenColor "#bbbbbb" "#cccccc" "^r(2x18)"
    , ppLayout = dzenColor "#ffffff" "" .
        (\x -> case x of
        "Hinted Tall" -> " ^fg(#777777)"
        "Hinted Wide" -> " ^fg(#777777)"
        "Hinted Full" -> " ^fg(#777777)"
        "Hinted ResizableTall" -> " ^fg(#777777)"
        "Hinted Mirror ResizableTall" -> " ^fg(#777777)"
        _ -> pad x
        )
    , ppOutput  = hPutStrLn h
    , ppTitle   = (' ':) . escape
    }
  where
    escape = concatMap (\x -> if x == '^' then "^^" else [x])
    pad = wrap " " " "
