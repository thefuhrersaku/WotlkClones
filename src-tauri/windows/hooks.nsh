; WOTLK Clones - hooks del instalador NSIS
;
; Crea el acceso directo en el escritorio por defecto en instalaciones GUI.
; (En instalaciones silenciosas/passive Tauri ya lo crea por su cuenta.)

!macro NSIS_HOOK_POSTINSTALL
  Call CreateOrUpdateDesktopShortcut
!macroend
