"""The remake's Options screen in the European languages (French, German, Italian, Spanish): the
English words as settings_screen.py writes them -> the words shown.  English and Japanese keep the
English.  (The remake's own screen: these are not the discs' texts.)  Key and button names, the
version names (US, JP, PS2 FDS, BizHawk, CRT, VSync) and numbers are left as they are."""

_ROWS = ('Controls', 'Options', 'Mods', 'Speedrun', 'Keyboard', 'Controller',
         'Route', 'Slot', 'Load State', 'Save State', 'Load Button', 'Save Button', 'Load Preset', 'Preset',
         'Up', 'Down', 'Left', 'Right', 'Jump', 'Attack / Talk', 'Item', 'Dash', 'Menu Shortcut',
         'Confirm Button', 'Reset Controls', 'Music Volume', 'Sound Volume', 'Window Size', 'Fullscreen',
         'Integer Scaling', 'Filter', 'Scanlines', 'Brightness Comp.', 'Balance', 'Language', 'Intro Movie',
         'Sprite Graphics', 'Level Top Fix', 'Reset Options', 'Text Speed', 'Instant Text', 'Rare Item Jingle',
         'Loading Pauses', 'Load Delay', 'Delay', 'L / R Swapping', 'Magic & Weapon Swap', 'Fixed Casino RNG',
         'Shadow Clipping', 'Character Clipping', 'No Death L.Sword', 'Reset Mods',
         'On', 'Off', 'New', 'Old', 'US & EU (Cross)', 'JP (Square)', 'Original', 'Instant', 'Custom', 'Normal',
         'Sharp', 'Smooth', 'Light', 'Medium', 'Heavy', 'High', 'Regular Item', 'Never', 'PC & HW', 'Hardware +1',
         'English', 'Japanese', 'French', 'German', 'Italian', 'Spanish', 'frames',
         'Enter bind  Del clear  < > keys / pad', 'Enter do / bind  Del clear  < > keys / pad',
         'Left / Right change    Esc back', 'Controls reset', 'Mods reset', 'Options reset', 'No state there',
         'Press a key (Esc cancels)', 'Press a button or stick (Esc cancels)', 'Menu shortcut keeps one key',
         'Cleared', 'Cancelled')

_WORDS = {
    'fr': ('Commandes', 'Options', 'Mods', 'Speedrun', 'Clavier', 'Manette',
           'Route', 'Emplacement', 'Charger état', 'Sauver état', 'Touche charger', 'Touche sauver', 'Charger préréglage', 'Préréglage',
           'Haut', 'Bas', 'Gauche', 'Droite', 'Sauter', 'Attaquer / Parler', 'Objet', 'Course', 'Raccourci menu',
           'Touche valider', 'Réinit. commandes', 'Volume musique', 'Volume sons', 'Taille fenêtre', 'Plein écran',
           'Échelle entière', 'Filtre', 'Lignes de balayage', 'Comp. luminosité', 'Équilibrage', 'Langue', 'Film d\'intro',
           'Graphismes sprites', 'Correctif haut niveau', 'Réinit. options', 'Vitesse du texte', 'Texte instantané', 'Jingle objet rare',
           'Pauses de chargement', 'Délai de chargement', 'Délai', 'Inverser L / R', 'Échange magie & arme', 'Casino RNG fixe',
           'Découpe des ombres', 'Découpe des persos', 'L.Épée sans mort', 'Réinit. mods',
           'Oui', 'Non', 'Nouveaux', 'Anciens', 'US & EU (Croix)', 'JP (Carré)', 'Original', 'Instantané', 'Perso', 'Normale',
           'Net', 'Lisse', 'Léger', 'Moyen', 'Fort', 'Élevé', 'Objet normal', 'Jamais', 'PC & HW', 'Matériel +1',
           'Anglais', 'Japonais', 'Français', 'Allemand', 'Italien', 'Espagnol', 'images',
           'Entrée assigner  Suppr effacer  < > clav. / man.', 'Entrée faire/assigner  Suppr eff.  < > clav./man.',
           'Gauche / Droite changer    Échap retour', 'Commandes réinitialisées', 'Mods réinitialisés', 'Options réinitialisées',
           'Aucun état ici', 'Appuyez sur une touche (Échap annule)', 'Appuyez sur un bouton ou stick (Échap annule)',
           'Le raccourci menu garde une touche', 'Effacé', 'Annulé'),
    'de': ('Steuerung', 'Optionen', 'Mods', 'Speedrun', 'Tastatur', 'Controller',
           'Route', 'Platz', 'Stand laden', 'Stand speichern', 'Taste Laden', 'Taste Speichern', 'Vorgabe laden', 'Vorgabe',
           'Oben', 'Unten', 'Links', 'Rechts', 'Springen', 'Angriff / Reden', 'Gegenstand', 'Rennen', 'Menü-Kürzel',
           'Bestätigen', 'Steuerung zurücks.', 'Musik', 'Soundeffekte', 'Fenstergröße', 'Vollbild',
           'Ganzz. Skalierung', 'Filter', 'Scanlines', 'Helligkeitsausgl.', 'Balance', 'Sprache', 'Intro-Film',
           'Sprite-Grafik', 'Level-Oben-Fix', 'Optionen zurücks.', 'Textgeschw.', 'Sofort-Text', 'Seltenes-Item-Jingle',
           'Ladepausen', 'Ladeverzögerung', 'Verzögerung', 'L / R tauschen', 'Magie & Waffe tauschen', 'Feste Casino-RNG',
           'Schatten-Clipping', 'Figuren-Clipping', 'L.Schwert ohne Tod', 'Mods zurücks.',
           'An', 'Aus', 'Neu', 'Alt', 'US & EU (Kreuz)', 'JP (Quadrat)', 'Original', 'Sofort', 'Eigene', 'Normal',
           'Scharf', 'Weich', 'Leicht', 'Mittel', 'Stark', 'Hoch', 'Normales Item', 'Nie', 'PC & HW', 'Hardware +1',
           'Englisch', 'Japanisch', 'Französisch', 'Deutsch', 'Italienisch', 'Spanisch', 'Frames',
           'Enter belegen  Entf löschen  < > Tastatur / Pad', 'Enter tun / belegen  Entf lösch.  < > Tast. / Pad',
           'Links / Rechts ändern    Esc zurück', 'Steuerung zurückgesetzt', 'Mods zurückgesetzt', 'Optionen zurückgesetzt',
           'Kein Stand dort', 'Taste drücken (Esc bricht ab)', 'Knopf oder Stick drücken (Esc bricht ab)',
           'Menü-Kürzel behält eine Taste', 'Gelöscht', 'Abgebrochen'),
    'it': ('Comandi', 'Opzioni', 'Mod', 'Speedrun', 'Tastiera', 'Controller',
           'Percorso', 'Slot', 'Carica stato', 'Salva stato', 'Tasto carica', 'Tasto salva', 'Carica preset', 'Preset',
           'Su', 'Giù', 'Sinistra', 'Destra', 'Salto', 'Attacco / Parla', 'Oggetto', 'Scatto', 'Scorciatoia menu',
           'Tasto conferma', 'Ripristina comandi', 'Volume musica', 'Volume effetti', 'Dim. finestra', 'Schermo intero',
           'Scala intera', 'Filtro', 'Scanline', 'Comp. luminosità', 'Bilanciamento', 'Lingua', 'Filmato intro',
           'Grafica sprite', 'Fix cima livello', 'Ripristina opzioni', 'Velocità testo', 'Testo istantaneo', 'Jingle oggetto raro',
           'Pause caricamento', 'Ritardo caricam.', 'Ritardo', 'Scambio L / R', 'Scambio magia & arma', 'RNG casinò fisso',
           'Taglio ombre', 'Taglio personaggi', 'Spada L. senza morti', 'Ripristina mod',
           'Sì', 'No', 'Nuova', 'Vecchia', 'US & EU (Croce)', 'JP (Quadrato)', 'Originale', 'Istantaneo', 'Person.', 'Normale',
           'Nitido', 'Morbido', 'Leggero', 'Medio', 'Forte', 'Alto', 'Oggetto normale', 'Mai', 'PC & HW', 'Hardware +1',
           'Inglese', 'Giapponese', 'Francese', 'Tedesco', 'Italiano', 'Spagnolo', 'fotogrammi',
           'Invio assegna  Canc cancella  < > tastiera / pad', 'Invio esegui/assegna  Canc canc.  < > tast./pad',
           'Sinistra / Destra cambia    Esc indietro', 'Comandi ripristinati', 'Mod ripristinate', 'Opzioni ripristinate',
           'Nessuno stato qui', 'Premi un tasto (Esc annulla)', 'Premi un pulsante o stick (Esc annulla)',
           'La scorciatoia menu tiene un tasto', 'Cancellato', 'Annullato'),
    'es': ('Controles', 'Opciones', 'Mods', 'Speedrun', 'Teclado', 'Mando',
           'Ruta', 'Ranura', 'Cargar estado', 'Guardar estado', 'Botón cargar', 'Botón guardar', 'Cargar preajuste', 'Preajuste',
           'Arriba', 'Abajo', 'Izquierda', 'Derecha', 'Saltar', 'Atacar / Hablar', 'Objeto', 'Carrera', 'Atajo menú',
           'Botón confirmar', 'Restablecer controles', 'Volumen música', 'Volumen sonido', 'Tamaño ventana', 'Pantalla completa',
           'Escala entera', 'Filtro', 'Scanlines', 'Comp. brillo', 'Equilibrio', 'Idioma', 'Vídeo intro',
           'Gráficos sprites', 'Ajuste cima nivel', 'Restablecer opciones', 'Velocidad texto', 'Texto instantáneo', 'Jingle objeto raro',
           'Pausas de carga', 'Retraso de carga', 'Retraso', 'Intercambiar L / R', 'Cambio magia & arma', 'RNG casino fijo',
           'Recorte sombras', 'Recorte personajes', 'Espada L. sin muertes', 'Restablecer mods',
           'Sí', 'No', 'Nuevos', 'Antiguos', 'US & EU (Cruz)', 'JP (Cuadrado)', 'Original', 'Instantáneo', 'Personal.', 'Normal',
           'Nítido', 'Suave', 'Ligero', 'Medio', 'Fuerte', 'Alto', 'Objeto normal', 'Nunca', 'PC & HW', 'Hardware +1',
           'Inglés', 'Japonés', 'Francés', 'Alemán', 'Italiano', 'Español', 'fotogramas',
           'Intro asignar  Supr borrar  < > teclado / mando', 'Intro hacer/asignar  Supr borr.  < > tecl./mando',
           'Izquierda / Derecha cambiar    Esc volver', 'Controles restablecidos', 'Mods restablecidos', 'Opciones restablecidas',
           'No hay estado ahí', 'Pulsa una tecla (Esc cancela)', 'Pulsa un botón o stick (Esc cancela)',
           'El atajo de menú conserva una tecla', 'Borrado', 'Cancelado'),
}
WORDS = {lang: dict(zip(_ROWS, w)) for lang, w in _WORDS.items()}
for _lang, _w in {'fr': ('Écran titre', 'Quitter le jeu ?', 'Oui', 'Non'), 'de': ('Titelbild', 'Spiel beenden?', 'Ja', 'Nein'),
                  'it': ('Schermata del titolo', 'Uscire dal gioco?', 'Sì', 'No'), 'es': ('Pantalla de título', '¿Salir del juego?', 'Sí', 'No')}.items():
    WORDS[_lang].update(zip(('Title Screen', 'Quit the game?', 'Yes', 'No'), _w))
assert all(len(w) == len(_ROWS) for w in _WORDS.values())


def tr(lang, s):
    """s in lang (fr / de / it / es), else s as it is."""
    d = WORDS.get(lang)
    if not d or not s: return s
    if s.endswith(' frames') and s[:-7].isdigit(): return f'{s[:-7]} {d["frames"]}'
    return d.get(s, s)
