/*
 * Carte « Tarifs Électricité » / "Tarifs Électricité" card
 * Servie automatiquement par l'intégration. type: custom:tarifs-electricite-card
 * Français si Home Assistant est en français, anglais sinon.
 */
const VERSION_CARTE = "1.1.0";

const COULEURS_PERIODE = {
  HP: "#f57c00",
  HC: "#2e7d32",
  HSC: "#6a1b9a",
  BASE: "#1976d2",
  PERSO: "#00897b",
  WE: "#7cb342",
  WE_HC: "#558b2f",
};
const COULEURS_TEMPO = { bleu: "#1e88e5", blanc: "#eceff1", rouge: "#e53935" };

// ------------------------------------------------------------------ textes
const TEXTES = {
  fr: {
    periode: {
      HP: "Heures pleines", HC: "Heures creuses", HSC: "Heures super creuses", BASE: "Base",
      PERSO: "Période spéciale", WE: "Week-end", WE_HC: "Week-end heures creuses", DYN: "Prix dynamique",
    },
    colonne: { HP: "HP", HC: "HC", HSC: "HSC", BASE: "Base" },
    ligne: { annee: "Toute l'année", hiver: "Hiver", ete: "Été", weekend: "Week-end", abonnement: "Abonnement" },
    tempo: { bleu: "Bleu", blanc: "Blanc", rouge: "Rouge" },
    jourTempo: (c) => (c ? `Jour ${c}` : "Jour inconnu"),
    maintenant: "maintenant",
    dans: (j, h, m) => (j ? `dans ${j} j ${h} h` : h ? `dans ${h} h ${String(m).padStart(2, "0")}` : `dans ${m} min`),
    a: "à",
    origine: "Origine",
    aujourdhuiCourt: "Auj.",
    demainCourt: "Dem.",
    maint: "maint.",
    heureCourte: (h) => `${h}h`,
    prixBas: "Prix bas",
    titreDefaut: "Tarif électricité",
    reglages: "Modifier le contrat",
    entiteIntrouvable: (e) => `Entité introuvable : ${e}<br>Ajoutez d'abord l'intégration « Tarifs Électricité ».`,
    minmax: (mn, mx) => `24 h : min ${mn} · max ${mx} €/kWh`,
    evolution: (d) => `Nouveaux prix le <b>${d}</b>`,
    enMoyenne: "en moyenne",
    prochaines: (h) => `Prochaines ${h} h`,
    joursSpeciaux: "Jours spéciaux",
    aujourdhui: "Aujourd'hui",
    demain: "Demain",
    normal: "Normal",
    jsAuto: "Suivi automatiquement depuis la source",
    jsAppui: "Appuyez pour changer",
    journee: (h) => `Journée de ${h} h à ${h} h`,
    dynSansPrevision: "La source ne publie pas les prix à venir : seule l'heure en cours est connue.",
    couleursTempo: "Couleurs Tempo",
    tempoIndispo: "Couleurs Tempo indisponibles pour le moment.",
    inconnue: "inconnue",
    officielle: "officielle",
    prevision: "prévision",
    legendeTempo: "Plein : couleur officielle · Pointillé : prévision",
    grille: "Grille tarifaire (€/kWh TTC)",
    marche: (src) => `Prix fixé heure par heure par le marché${src ? ` (source : ${src})` : ""}.`,
    abonnement: (v, kva) => `Abonnement : ${v} €/mois${kva ? ` · ${kva} kVA` : ""}`,
    puissance: (kva) => `Puissance souscrite : ${kva} kVA`,
    maConso: "Ma consommation",
    calcul: "Calcul en cours…",
    pasDeDonnees: "Aucune statistique pour ce compteur : il doit avoir une classe d'état total ou total_increasing et au moins une heure d'historique.",
    indispo: "Données indisponibles.",
    semaine: "Semaine",
    mois: "Mois",
    annee: "Année",
    detailTuile: (e, a) => `Énergie ${e} € + abonnement ${a} €`,
    tousMontants: (v) => `Tous les montants comprennent l'abonnement (${v} €/mois), au prorata de la période.`,
    dontAbo: (v) => `dont abonnement ${v} €`,
    factureEnCours: "Facture en cours",
    depuisLe: (d) => `depuis le ${d}`,
    estimeeAu: (d) => `Estimée au ${d}`,
    dansJours: (n) => `dans ${n} j`,
    projection: (n, v) => `Projection d'après les ${n} derniers jours (${v} €/jour hors abonnement).`,
    coutAnnuel: "Coût annuel estimé",
    fiabilite: { bonne: "fiable", moyenne: "fiabilité moyenne", faible: "peu fiable" },
    parFacture: (v, abo, freq, kwh, j, extra) =>
      `Soit ≈ ${v} € par facture${abo ? " (abonnement compris)" : ""} (${freq}) · ${kwh} kWh/an, d'après ${j} jours${extra ? " extrapolés sur un an" : ""}`,
    frequence: { 1: "tous les mois", 2: "tous les 2 mois", 3: "tous les 3 mois", 6: "tous les 6 mois", 12: "une fois par an" },
    estimationInsuffisante: "Estimation annuelle : il faut au moins 14 jours de consommation.",
    mensualiteEstimee: "Mensualité estimée",
    prelevements: (n, f) => `${n} prélèvements, ${f}`,
    aboParPrelevement: (v) => `abonnement compris (${v} € par prélèvement)`,
    prelevee: "Prélevée par le fournisseur",
    ecart: "Écart",
    parMois: "€/mois",
    conseil: (code, ecart, fiab) => {
      const prudence = fiab === "bonne" ? "" : " (estimation encore peu fiable : moins d'un an de données)";
      if (code === "ok") return `Votre mensualité correspond à votre consommation.${prudence}`;
      if (code === "trop_basse")
        return `Votre mensualité semble trop basse d'environ ${Math.round(ecart)} €/mois : attendez-vous à une facture de régularisation, ou demandez à l'augmenter.${prudence}`;
      return `Votre mensualité semble trop élevée d'environ ${Math.round(-ecart)} €/mois : vous pouvez demander à votre fournisseur de la baisser.${prudence}`;
    },
    dapres: (j, extra, kwh, an) =>
      `D'après ${j} jours de consommation${extra ? " (extrapolés sur un an)" : ""} · ${kwh} kWh/an · ${an} €/an`,
    mensualiteInsuffisante: (n) => `Mensualité : il faut au moins 14 jours de consommation (${n} pour l'instant).`,
    solde: (d, p, c) => `Depuis le ${d} : payé ≈ ${p} €, consommé ${c} €`,
    enAvance: "Vous êtes en avance : remboursement probable.",
    enRetard: "Vous êtes en retard : régularisation probable.",
    incomplet: " Historique du compteur incomplet sur la période.",
    corriges: (n) => `${n} relevé(s) aberrant(s) du compteur ignoré(s) (saut d'index).`,
    statut: { en_cours: "En cours", prevue: "Prévue", passee: "Passée" },
    aPartirDu: (d) => `À partir du ${d}`,
    grilleOrigine: "Grille d'origine",
    aucunPrix: "Aucun prix modifié",
    historique: (n) => `Historique des prix (${n} grilles)`,
    editeur: {
      entity: "Capteur « Prix actuel » du contrat",
      titre: "Titre (par défaut : fournisseur · offre)",
      heures: "Durée de la frise",
      afficher_frise: "Afficher la frise des prochaines heures",
      afficher_tempo: "Afficher les couleurs Tempo (offres Tempo)",
      afficher_grille: "Afficher la grille tarifaire",
      afficher_historique: "Afficher l'historique des prix",
      afficher_suivi: "Afficher ma consommation (coûts, mensualité)",
    },
  },
  en: {
    periode: {
      HP: "Peak hours", HC: "Off-peak hours", HSC: "Super off-peak", BASE: "Flat rate",
      PERSO: "Special period", WE: "Weekend", WE_HC: "Weekend off-peak", DYN: "Dynamic price",
    },
    colonne: { HP: "Peak", HC: "Off-peak", HSC: "Super off-peak", BASE: "Flat" },
    ligne: { annee: "All year", hiver: "Winter", ete: "Summer", weekend: "Weekend", abonnement: "Standing charge" },
    tempo: { bleu: "Blue", blanc: "White", rouge: "Red" },
    jourTempo: (c) => (c ? `${{ bleu: "Blue", blanc: "White", rouge: "Red" }[c] || c} day` : "Unknown day"),
    maintenant: "now",
    dans: (j, h, m) => (j ? `in ${j} d ${h} h` : h ? `in ${h} h ${String(m).padStart(2, "0")}` : `in ${m} min`),
    a: "at",
    origine: "Origin",
    aujourdhuiCourt: "Today",
    demainCourt: "Tmrw",
    maint: "now",
    heureCourte: (h) => `${h}:00`,
    prixBas: "Low price",
    titreDefaut: "Electricity rate",
    reglages: "Edit contract",
    entiteIntrouvable: (e) => `Entity not found: ${e}<br>Add the “Tarifs Électricité” integration first.`,
    minmax: (mn, mx) => `24 h: min ${mn} · max ${mx} €/kWh`,
    evolution: (d) => `New prices from <b>${d}</b>`,
    enMoyenne: "on average",
    prochaines: (h) => `Next ${h} h`,
    joursSpeciaux: "Special days",
    aujourdhui: "Today",
    demain: "Tomorrow",
    normal: "Normal",
    jsAuto: "Followed automatically from the source",
    jsAppui: "Tap to change",
    journee: (h) => `Day runs from ${h}:00 to ${h}:00`,
    dynSansPrevision: "The source does not publish upcoming prices: only the current hour is known.",
    couleursTempo: "Tempo colours",
    tempoIndispo: "Tempo colours are not available right now.",
    inconnue: "unknown",
    officielle: "official",
    prevision: "forecast",
    legendeTempo: "Solid: official colour · Dashed: forecast",
    grille: "Price grid (€/kWh incl. tax)",
    marche: (src) => `Price set hour by hour by the market${src ? ` (source: ${src})` : ""}.`,
    abonnement: (v, kva) => `Standing charge: ${v} €/month${kva ? ` · ${kva} kVA` : ""}`,
    puissance: (kva) => `Subscribed power: ${kva} kVA`,
    maConso: "My consumption",
    calcul: "Calculating…",
    pasDeDonnees: "No statistics for this meter: it needs a total or total_increasing state class and at least one hour of history.",
    indispo: "Data unavailable.",
    semaine: "Week",
    mois: "Month",
    annee: "Year",
    detailTuile: (e, a) => `Energy ${e} € + standing charge ${a} €`,
    tousMontants: (v) => `All amounts include the standing charge (${v} €/month), pro rata.`,
    dontAbo: (v) => `incl. standing charge ${v} €`,
    factureEnCours: "Current bill",
    depuisLe: (d) => `since ${d}`,
    estimeeAu: (d) => `Estimated on ${d}`,
    dansJours: (n) => `in ${n} d`,
    projection: (n, v) => `Projected from the last ${n} days (${v} €/day excl. standing charge).`,
    coutAnnuel: "Estimated yearly cost",
    fiabilite: { bonne: "reliable", moyenne: "fair reliability", faible: "low reliability" },
    parFacture: (v, abo, freq, kwh, j, extra) =>
      `About ${v} € per bill${abo ? " (standing charge incl.)" : ""} (${freq}) · ${kwh} kWh/year, from ${j} days${extra ? " extrapolated to a year" : ""}`,
    frequence: { 1: "monthly", 2: "every 2 months", 3: "every 3 months", 6: "every 6 months", 12: "yearly" },
    estimationInsuffisante: "Yearly estimate: at least 14 days of consumption are needed.",
    mensualiteEstimee: "Estimated instalment",
    prelevements: (n, f) => `${n} payments, ${f}`,
    aboParPrelevement: (v) => `standing charge incl. (${v} € per payment)`,
    prelevee: "Charged by the supplier",
    ecart: "Difference",
    parMois: "€/month",
    conseil: (code, ecart, fiab) => {
      const prudence = fiab === "bonne" ? "" : " (estimate not yet reliable: less than a year of data)";
      if (code === "ok") return `Your instalment matches your consumption.${prudence}`;
      if (code === "trop_basse")
        return `Your instalment looks about ${Math.round(ecart)} €/month too low: expect a balancing bill, or ask to raise it.${prudence}`;
      return `Your instalment looks about ${Math.round(-ecart)} €/month too high: you can ask your supplier to lower it.${prudence}`;
    },
    dapres: (j, extra, kwh, an) =>
      `From ${j} days of consumption${extra ? " (extrapolated to a year)" : ""} · ${kwh} kWh/year · ${an} €/year`,
    mensualiteInsuffisante: (n) => `Instalment: at least 14 days of consumption are needed (${n} so far).`,
    solde: (d, p, c) => `Since ${d}: paid ≈ ${p} €, used ${c} €`,
    enAvance: "You are ahead: a refund is likely.",
    enRetard: "You are behind: a balancing bill is likely.",
    incomplet: " Meter history is incomplete for this period.",
    corriges: (n) => `${n} abnormal meter reading(s) ignored (index jump).`,
    statut: { en_cours: "Current", prevue: "Upcoming", passee: "Past" },
    aPartirDu: (d) => `From ${d}`,
    grilleOrigine: "Original grid",
    aucunPrix: "No price changed",
    historique: (n) => `Price history (${n} grids)`,
    editeur: {
      entity: "Contract's “Current price” sensor",
      titre: "Title (default: supplier · offer)",
      heures: "Timeline length",
      afficher_frise: "Show the upcoming hours timeline",
      afficher_tempo: "Show Tempo colours (Tempo offers)",
      afficher_grille: "Show the price grid",
      afficher_historique: "Show price history",
      afficher_suivi: "Show my consumption (costs, bills)",
    },
  },
};

function langue(hass) {
  const l = (hass?.locale?.language || hass?.language || navigator.language || "en").toLowerCase();
  return l.startsWith("fr") ? "fr" : "en";
}

/** Formats et textes dans la langue de l'utilisateur. */
function outils(hass) {
  const code = langue(hass);
  const T = TEXTES[code];
  const loc = hass?.locale?.language || (code === "fr" ? "fr-FR" : "en-GB");
  const euro = (v, d = 4) =>
    v === null || v === undefined || isNaN(v)
      ? "—"
      : Number(v).toLocaleString(loc, { minimumFractionDigits: d, maximumFractionDigits: d });
  const nombre = (v, d = 0) => Number(v ?? 0).toLocaleString(loc, { maximumFractionDigits: d });
  const heure = (iso) => new Date(iso).toLocaleTimeString(loc, { hour: "2-digit", minute: "2-digit" });
  const date = (iso) => {
    if (!iso) return T.origine;
    const txt = new Date(iso + "T12:00:00").toLocaleDateString(loc, { day: "numeric", month: "long", year: "numeric" });
    return code === "fr" ? txt.replace(/^1 /, "1er ") : txt;
  };
  const pct = (v) =>
    v === null || v === undefined ? "" : `${v > 0 ? "+" : ""}${Number(v).toLocaleString(loc)} %`;
  const dans = (iso) => {
    const ms = new Date(iso) - new Date();
    if (ms <= 0) return T.maintenant;
    const min = Math.round(ms / 60000);
    return T.dans(Math.floor(min / 1440), Math.floor((min % 1440) / 60), min % 60);
  };
  const jourCourt = (iso) => {
    const d = new Date(iso + "T12:00:00");
    const auj = new Date();
    auj.setHours(12, 0, 0, 0);
    const ecart = Math.round((d - auj) / 86400000);
    if (ecart === 0) return T.aujourdhuiCourt;
    if (ecart === 1) return T.demainCourt;
    return d.toLocaleDateString(loc, { weekday: "short", day: "numeric" });
  };
  return { code, T, euro, nombre, heure, date, pct, dans, jourCourt };
}

// Vert → orange → rouge selon la place du prix entre min et max
function couleurPrix(prix, min, max) {
  if (prix === null || prix === undefined) return "var(--disabled-text-color, #bbb)";
  const r = max > min ? Math.min(1, Math.max(0, (prix - min) / (max - min))) : 0.5;
  return `hsl(${120 - 120 * r}, 65%, 45%)`;
}

const echapper = (t) =>
  String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

class TarifsElectriciteCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("tarifs-electricite-card-editor");
  }

  static getStubConfig(hass) {
    const id =
      Object.keys(hass.states).find((e) => e.startsWith("sensor.tarif_electricite_prix_actuel")) ||
      "sensor.tarif_electricite_prix_actuel";
    return { entity: id };
  }

  setConfig(config) {
    this._config = {
      heures: 24,
      afficher_frise: false,
      afficher_tempo: false,
      afficher_grille: false,
      afficher_historique: false,
      afficher_suivi: false,
      ...config,
    };
    if (!this._config.entity) this._config.entity = "sensor.tarif_electricite_prix_actuel";
    this._dernier = null;
    this._rendu();
  }

  set hass(hass) {
    const changementLangue = langue(hass) !== langue(this._hass);
    this._hass = hass;
    const st = hass.states[this._config?.entity];
    if (st !== this._dernier || changementLangue) {
      this._dernier = st;
      this._rendu();
    }
  }

  connectedCallback() {
    this._minuteur = setInterval(() => this._rendu(), 60000);
  }

  disconnectedCallback() {
    clearInterval(this._minuteur);
  }

  getCardSize() {
    return 5;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _ouvrirReglages() {
    history.pushState(null, "", "/config/integrations/integration/tarifs_electricite");
    window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
  }

  _plusInfo() {
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId: this._config.entity },
        bubbles: true,
        composed: true,
      })
    );
  }

  /** Nom de période traduit, avec le nom personnalisé et le jour spécial. */
  _periode(o, a, periode, jourSpecial) {
    let nom = o.T.periode[periode] || periode || "—";
    if (periode === "PERSO") {
      const perso = (a.grille?.colonnes || []).find((c) => c.cle === "PERSO")?.nom;
      if (perso) nom = perso;
    }
    return jourSpecial ? `${nom} · ${jourSpecial}` : nom;
  }

  _frise(o, a) {
    const previsions = a.previsions;
    const heures = Number(this._config.heures) || 24;
    if (!previsions?.length) return "";
    const debut = new Date(previsions[0].debut);
    const fin = new Date(debut.getTime() + heures * 3600000);
    const total = fin - debut;
    const connus = previsions.map((s) => s.prix).filter((p) => p !== null && p !== undefined);
    const pmin = Math.min(...connus);
    const pmax = Math.max(...connus);
    const blocs = previsions
      .filter((s) => new Date(s.debut) < fin)
      .map((s) => {
        const d = Math.max(new Date(s.debut), debut);
        const f = Math.min(new Date(s.fin), fin);
        const largeur = ((f - d) / total) * 100;
        let fond = COULEURS_PERIODE[s.periode] || "#888";
        let bord = "";
        if (s.periode === "DYN") {
          fond = couleurPrix(s.prix, pmin, pmax);
        } else if (s.jour_special) {
          bord = "background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.35) 0 3px,transparent 3px 7px);box-shadow:inset 0 -3px 0 #c62828;";
        }
        if (s.couleur) {
          fond = COULEURS_TEMPO[s.couleur];
          if (s.periode === "HC") bord = "background-image:repeating-linear-gradient(135deg,rgba(0,0,0,.18) 0 4px,transparent 4px 8px);";
        } else if (s.periode !== "BASE" && s.prix === null) {
          fond = "var(--disabled-text-color, #bbb)";
        }
        const couleur = s.couleur ? ` ${o.T.tempo[s.couleur] || s.couleur}` : "";
        const titre = `${this._periode(o, a, s.periode, s.jour_special)}${couleur} · ${o.heure(s.debut)} → ${o.heure(s.fin)} · ${o.euro(s.prix)} €/kWh`;
        return `<div class="bloc" style="width:${largeur}%;background:${fond};${bord}" title="${echapper(titre)}"></div>`;
      })
      .join("");
    const pas = heures > 24 ? 12 : 6;
    let reperes = "";
    const premier = new Date(debut);
    premier.setMinutes(0, 0, 0);
    premier.setHours(Math.ceil((debut.getHours() + (debut.getMinutes() ? 1 : 0)) / pas) * pas);
    for (let t = premier; t < fin; t = new Date(t.getTime() + pas * 3600000)) {
      const pos = ((t - debut) / total) * 100;
      if (pos < 12 || pos > 96) continue;
      reperes += `<span class="repere" style="left:${pos}%">${o.T.heureCourte(t.getHours())}</span>`;
    }
    return `<div class="frise">${blocs}</div><div class="reperes"><span class="repere" style="left:0;transform:none">${o.T.maint}</span>${reperes}</div>`;
  }

  _tempo(o, a) {
    const prev = a.tempo_previsions || [];
    if (!prev.length) return `<div class="tempo vide">${o.T.tempoIndispo}</div>`;
    return `<div class="tempo">${prev
      .slice(0, 9)
      .map((p) => {
        let c = COULEURS_TEMPO[p.couleur] || "transparent";
        if (!p.confirmee && p.couleur === "blanc") c = "#90a4ae";
        const classe = p.confirmee ? "pastille" : "pastille prevue";
        const titre = `${o.T.tempo[p.couleur] || o.T.inconnue} (${p.confirmee ? o.T.officielle : o.T.prevision})`;
        return `<div class="jour"><span>${o.jourCourt(p.date)}</span><div class="${classe}" style="--c:${c}" title="${titre}"></div></div>`;
      })
      .join("")}</div>
      <div class="legende">${o.T.legendeTempo}</div>`;
  }

  /** Nom d'une ligne de grille (saison, week-end, couleur Tempo, ou jour spécial saisi). */
  _ligne(o, l) {
    if (COULEURS_TEMPO[l.code || l.libelle]) return o.T.tempo[l.code || l.libelle];
    if (l.code && o.T.ligne[l.code]) return o.T.ligne[l.code];
    return l.libelle;
  }

  _grille(o, a) {
    const g = a.grille || {};
    const lignes = g.lignes || [];
    const cols = g.colonnes || [];
    if (!lignes.length) {
      return a.type_offre === "dynamique" ? `<div class="discret">${o.T.marche(a.source_prix)}</div>` : "";
    }
    const nomCol = (c) => (c.cle === "PERSO" ? echapper(c.nom) : o.T.colonne[c.cle] || c.cle);
    const entete = cols.map((c) => `<th>${nomCol(c)}</th>`).join("");
    const corps = lignes
      .map((l) => {
        const nom = echapper(this._ligne(o, l));
        const code = l.code || l.libelle;
        let lib = nom;
        if (COULEURS_TEMPO[code]) lib = `<span class="puce" style="--c:${COULEURS_TEMPO[code]}"></span>${nom}`;
        else if (l.special) lib = `<ha-icon class="petite" icon="mdi:calendar-alert"></ha-icon>${nom}`;
        let actif;
        if (a.couleur_tempo) actif = code === a.couleur_tempo;
        else if (a.jour_special) actif = l.libelle === a.jour_special;
        else if (a.periode === "WE" || a.periode === "WE_HC") actif = code === "weekend" || l.libelle === "Week-end";
        else if (a.saison) actif = code === a.saison;
        else actif = lignes.indexOf(l) === 0;
        const periodeCol =
          a.periode === "WE" ? (cols.some((c) => c.cle === "HP") ? "HP" : "BASE")
          : a.periode === "WE_HC" ? "HC" : a.periode;
        const cellules = cols
          .map((c) => {
            const surligne = actif && c.cle === periodeCol ? ' class="actif"' : "";
            return `<td${surligne}>${l.prix[c.cle] === undefined ? "" : o.euro(l.prix[c.cle])}</td>`;
          })
          .join("");
        return `<tr><td class="lib">${lib}</td>${cellules}</tr>`;
      })
      .join("");
    const abo =
      a.abonnement_mensuel != null
        ? `<div class="abo">${o.T.abonnement(o.euro(a.abonnement_mensuel, 2), a.puissance_kva)}</div>`
        : a.puissance_kva
          ? `<div class="abo">${o.T.puissance(a.puissance_kva)}</div>`
          : "";
    return `<table><thead><tr><th></th>${entete}</tr></thead><tbody>${corps}</tbody></table>${abo}`;
  }

  _suivi(o, a) {
    const s = a.suivi;
    if (!s) return "";
    const { T, euro, nombre, date } = o;
    // L'abonnement est compté dans tous les montants : on le dit, et combien
    const avecAbo = a.abonnement_mensuel != null && a.abonnement_mensuel > 0;
    const dont = (v) => (avecAbo && v != null ? `<div class="dont">${T.dontAbo(euro(v, 2))}</div>` : "");
    if (s.etat !== "ok") {
      const msg = s.etat === "en_attente" ? T.calcul : s.etat === "pas_de_donnees" ? T.pasDeDonnees : T.indispo;
      return `<div class="section"><h4>${T.maConso}</h4><div class="discret">${msg}</div></div>`;
    }
    const tuile = (cle, titre) => {
      const p = s[cle] || {};
      const detail = avecAbo ? ` title="${T.detailTuile(euro(p.cout_energie, 2), euro(p.cout_abonnement, 2))}"` : "";
      return `<div class="tuile"${detail}><span class="t-titre">${titre}</span><span class="t-val">${euro(p.total, 2)} €</span>
        <span class="t-kwh">${nombre(p.kwh, 1)} kWh</span></div>`;
    };
    const e = s.estimation || {};
    const fiab = T.fiabilite[e.fiabilite] || e.fiabilite;
    let mensu = "";
    if (s.mode_paiement === "conso_reelle") {
      const f = s.facture;
      if (f) {
        mensu += `<div class="mensualite">
          <div class="m-ligne"><span>${T.factureEnCours} <span class="discret">(${T.depuisLe(date(f.debut))})</span></span><b>${euro(f.montant_actuel, 2)} €</b></div>
          ${dont(f.abonnement_actuel)}
          <div class="m-ligne"><span>${T.estimeeAu(date(f.prochaine_facture))} <span class="discret">(${T.dansJours(Math.ceil(f.jours_restants))})</span></span><b>≈ ${euro(f.montant_estime, 2)} €</b></div>
          ${dont(f.abonnement_estime)}
          <div class="legende">${T.projection(Math.min(14, Math.ceil(f.jours_ecoules)), euro(f.cout_moyen_par_jour, 2))}</div>
        </div>`;
      }
      if (e.cout_annuel_estime != null) {
        mensu += `<div class="m-ligne" style="margin-top:8px"><span>${T.coutAnnuel} <span class="discret">(${fiab})</span></span><b>${euro(e.cout_annuel_estime, 2)} €</b></div>
          ${dont(e.cout_abonnement_annuel)}
          <div class="legende">${T.parFacture(euro(e.facture_moyenne_estimee, 2), avecAbo, T.frequence[s.frequence_mois] || "", nombre(e.consommation_annuelle_kwh), e.jours_de_donnees, e.extrapole)}</div>`;
      } else if (e.fiabilite === "insuffisante") {
        mensu += `<div class="legende">${T.estimationInsuffisante}</div>`;
      }
    } else if (e.mensualite_estimee != null) {
      let ecart = "";
      if (e.mensualite_fournisseur != null) {
        const cls = Math.abs(e.ecart_pct) <= 5 ? "ok" : e.ecart_mensuel > 0 ? "hausse" : "baisse";
        const code = e.conseil_code || (Math.abs(e.ecart_pct) <= 5 ? "ok" : e.ecart_mensuel > 0 ? "trop_basse" : "trop_haute");
        ecart = `<div class="m-ligne"><span>${T.prelevee}</span><span>${euro(e.mensualite_fournisseur, 2)} €</span></div>
          <div class="m-ligne"><span>${T.ecart}</span><span class="${cls}">${e.ecart_mensuel > 0 ? "+" : ""}${euro(e.ecart_mensuel, 2)} ${T.parMois} (${o.pct(e.ecart_pct)})</span></div>
          <div class="conseil">${T.conseil(code, e.ecart_mensuel, e.fiabilite)}</div>`;
      }
      mensu = `<div class="mensualite">
        <div class="m-ligne"><span>${T.mensualiteEstimee} <span class="discret">(${T.prelevements(e.prelevements_par_an, fiab)})</span></span><b>${euro(e.mensualite_estimee, 2)} €</b></div>
        ${avecAbo ? `<div class="dont">${T.aboParPrelevement(euro(e.cout_abonnement_annuel / e.prelevements_par_an, 2))}</div>` : ""}
        ${ecart}
        <div class="legende">${T.dapres(e.jours_de_donnees, e.extrapole, nombre(e.consommation_annuelle_kwh), euro(e.cout_annuel_estime, 2))}</div>
      </div>`;
    } else if (e.fiabilite === "insuffisante") {
      mensu = `<div class="legende">${T.mensualiteInsuffisante(e.jours_de_donnees || 0)}</div>`;
    }
    let solde = "";
    if (s.solde) {
      const v = s.solde.solde;
      solde = `<div class="m-ligne solde"><span>${T.solde(date(s.solde.depuis), euro(s.solde.paye_estime, 2), euro(s.solde.consomme, 2))}</span>
        <span class="${v >= 0 ? "baisse" : "hausse"}">${v >= 0 ? "+" : ""}${euro(v, 2)} €</span></div>
        <div class="legende">${v >= 0 ? T.enAvance : T.enRetard}${s.solde.donnees_completes ? "" : T.incomplet}</div>`;
    }
    const corrige = s.heures_corrigees ? `<div class="legende">${T.corriges(s.heures_corrigees)}</div>` : "";
    return `<div class="section"><h4>${T.maConso}</h4>
      <div class="tuiles">${tuile("aujourdhui", T.aujourdhui)}${tuile("semaine", T.semaine)}${tuile("mois", T.mois)}${tuile("annee", T.annee)}</div>
      ${avecAbo ? `<div class="legende">${T.tousMontants(euro(a.abonnement_mensuel, 2))}</div>` : ""}
      ${mensu}${solde}${corrige}</div>`;
  }

  _historique(o, a) {
    const h = a.historique_prix || [];
    if (h.length < 2) return "";
    const { T, euro, pct, date } = o;
    const lignes = h
      .slice()
      .reverse()
      .map((v) => {
        const vars = (v.variations || [])
          .map((x) => {
            const abo = x.code === "abonnement" || x.libelle === "Abonnement";
            const colonne = (a.grille?.colonnes || []).find((c) => c.cle === x.cle);
            const col = colonne ? (colonne.cle === "PERSO" ? colonne.nom : T.colonne[colonne.cle] || colonne.cle) : x.cle;
            const ligne = this._ligne(o, x);
            const lib = abo ? T.ligne.abonnement : `${x.code === "annee" || x.libelle === "Toute l'année" ? "" : ligne + " "}${col}`;
            const d = abo ? 2 : 4;
            return `<div class="var"><span>${echapper(lib)}</span><span>${euro(x.avant, d)} → <b>${euro(x.apres, d)}</b> <span class="${x.variation_pct > 0 ? "hausse" : "baisse"}">${pct(x.variation_pct)}</span></span></div>`;
          })
          .join("");
        const offre = v.offre !== a.offre ? `<div class="discret">${echapper(v.fournisseur)} – ${echapper(v.offre)}</div>` : "";
        return `<div class="version ${v.statut}">
          <div class="v-tete"><b>${v.date_effet ? T.aPartirDu(date(v.date_effet)) : T.grilleOrigine}</b>
          <span class="statut">${T.statut[v.statut]}</span></div>${offre}
          ${vars || (v.date_effet ? `<div class="discret">${T.aucunPrix}</div>` : "")}</div>`;
      })
      .join("");
    return `<details class="historique"${this._histOuvert ? " open" : ""}><summary>${T.historique(h.length)}</summary>${lignes}</details>`;
  }

  _joursSpeciaux(o, a) {
    const js = a.jours_speciaux;
    if (!js) return "";
    const { T } = o;
    const puce = (quand, titre) => {
      const val = js[quand];
      const auto = js[`auto_${quand}`];
      const special = val && val !== "Normal";
      const affiche = special ? echapper(val) : T.normal;
      return `<div class="js ${special ? "special" : ""} ${auto ? "auto" : ""}" data-quand="${quand}"
        title="${auto ? T.jsAuto : T.jsAppui}">
        <span class="js-titre">${titre}</span>
        <span class="js-val">${special ? "⚠ " : ""}${affiche}${auto ? ' <ha-icon class="petite" icon="mdi:link-variant"></ha-icon>' : ""}</span>
      </div>`;
    };
    const debut = js.debut_h ? `<div class="legende">${T.journee(js.debut_h)}</div>` : "";
    return `<div class="js-ligne">${puce("aujourdhui", T.aujourdhui)}${puce("demain", T.demain)}</div>${debut}`;
  }

  _changerJour(quand) {
    const js = this._hass?.states[this._config.entity]?.attributes?.jours_speciaux;
    if (!js || js[`auto_${quand}`]) return;
    const opts = js.options || [];
    const suivant = opts[(opts.indexOf(js[quand]) + 1) % opts.length];
    this._hass.callService("select", "select_option", {
      entity_id: `select.tarif_electricite_jour_special_${quand}`,
      option: suivant,
    });
  }

  _rendu() {
    if (!this._config) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const o = outils(this._hass);
    const { T, euro } = o;
    const st = this._hass?.states[this._config.entity];
    if (!st) {
      this.shadowRoot.innerHTML = `<ha-card><div class="contenu">${T.entiteIntrouvable(echapper(this._config.entity))}</div></ha-card>`;
      return;
    }
    const a = st.attributes;
    const prix = st.state === "unknown" || st.state === "unavailable" ? null : Number(st.state);
    const periode = a.periode;
    let couleurPeriode = COULEURS_PERIODE[periode] || "#888";
    if (periode === "DYN") couleurPeriode = couleurPrix(prix, a.prix_min_24h, a.prix_max_24h);
    if (a.jour_special) couleurPeriode = "#c62828";
    const titre = this._config.titre || [a.fournisseur, a.offre].filter(Boolean).join(" · ");
    const estTempo = a.type_offre === "tempo";

    const badgeTempo = estTempo
      ? `<span class="badge tempo-badge" style="--c:${COULEURS_TEMPO[a.couleur_tempo] || "#999"}">${T.jourTempo(a.couleur_tempo && (o.code === "fr" ? a.couleur_tempo : a.couleur_tempo))}</span>`
      : "";

    let prochain = "";
    if (a.prochain_changement) {
      // Le jour spécial éventuel figure après « · » dans le libellé calculé
      const special = (a.prochaine_periode_libelle || "").split(" · ")[1];
      prochain = `<div class="prochain">
        <ha-icon icon="mdi:arrow-right-circle-outline"></ha-icon>
        <span><b>${echapper(a.prochaine_periode ? this._periode(o, a, a.prochaine_periode, special) : a.prochaine_periode_libelle || "")}</b> ${T.a} ${o.heure(a.prochain_changement)}
        <span class="discret">(${o.dans(a.prochain_changement)})</span> · ${euro(a.prochain_prix)} €/kWh</span></div>`;
    }

    // Min/max : seulement pour le prix dynamique
    const minmax =
      a.type_offre === "dynamique" && a.prix_min_24h != null
        ? `<div class="minmax">${T.minmax(euro(a.prix_min_24h), euro(a.prix_max_24h))}</div>`
        : "";

    const evo = a.evolution_prevue;
    const evolution = evo
      ? `<div class="evolution"><ha-icon icon="mdi:calendar-arrow-right"></ha-icon><span>${T.evolution(o.date(evo.date_effet))}${evo.variation_moyenne_pct != null ? ` · <span class="${evo.variation_moyenne_pct > 0 ? "hausse" : "baisse"}">${o.pct(evo.variation_moyenne_pct)}</span> ${T.enMoyenne}` : ""}</span></div>`
      : "";

    this.shadowRoot.innerHTML = `
      <style>
        ha-card { overflow: hidden; }
        .entete { display:flex; align-items:center; gap:10px; padding:14px 16px 0; }
        .entete ha-icon { color: var(--primary-color); }
        .titre { flex:1; font-weight:600; font-size:1.05em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .reglages { cursor:pointer; color: var(--secondary-text-color); --mdc-icon-size:20px; }
        .contenu { padding: 8px 16px 16px; }
        .principal { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; cursor:pointer; }
        .prix { font-size:2.4em; font-weight:700; line-height:1.1; }
        .unite { font-size:.4em; font-weight:400; color: var(--secondary-text-color); margin-left:4px; }
        .badge { padding:3px 10px; border-radius:12px; font-size:.85em; font-weight:600; color:#fff; background: var(--c); }
        .tempo-badge { color: #111; border:1px solid rgba(0,0,0,.2); }
        .prochain { display:flex; align-items:center; gap:6px; margin-top:6px; color: var(--primary-text-color); --mdc-icon-size:18px; }
        .discret, .minmax, .legende, .abo { color: var(--secondary-text-color); font-size:.85em; }
        .minmax { margin-top:2px; }
        .section { margin-top:14px; }
        .section h4 { margin:0 0 6px; font-size:.8em; text-transform:uppercase; letter-spacing:.05em; color: var(--secondary-text-color); font-weight:600; }
        .frise { display:flex; height:18px; border-radius:6px; overflow:hidden; background: var(--divider-color); }
        .bloc { height:100%; min-width:1px; }
        .reperes { position:relative; height:16px; font-size:.72em; color: var(--secondary-text-color); }
        .repere { position:absolute; top:2px; transform:translateX(-50%); white-space:nowrap; }
        .tempo { display:flex; gap:8px; flex-wrap:wrap; }
        .tempo.vide { color: var(--secondary-text-color); font-size:.9em; }
        .jour { display:flex; flex-direction:column; align-items:center; gap:3px; font-size:.75em; color: var(--secondary-text-color); min-width:34px; }
        .pastille { width:22px; height:22px; border-radius:50%; background: var(--c); border:1px solid rgba(0,0,0,.25); }
        .pastille.prevue { background: transparent; border:3px dashed var(--c); width:16px; height:16px; }
        .legende { margin-top:4px; font-size:.75em; }
        table { width:100%; border-collapse:collapse; font-size:.9em; }
        th { text-align:right; font-weight:600; color: var(--secondary-text-color); padding:2px 6px; }
        td { text-align:right; padding:4px 6px; border-top:1px solid var(--divider-color); font-variant-numeric: tabular-nums; }
        td.lib { text-align:left; }
        td.actif { font-weight:700; color: var(--primary-color); }
        .puce { display:inline-block; width:10px; height:10px; border-radius:50%; background: var(--c); border:1px solid rgba(0,0,0,.25); margin-right:6px; }
        .abo { margin-top:6px; }
        .bas { background:#2e7d32; }
        .evolution { display:flex; align-items:center; gap:6px; margin-top:8px; padding:6px 10px; border-radius:8px; background: rgba(3,169,244,.1); font-size:.9em; --mdc-icon-size:18px; }
        .hausse { color:#c62828; font-weight:600; }
        .baisse { color:#2e7d32; font-weight:600; }
        .historique { margin-top:12px; font-size:.9em; }
        .historique summary { cursor:pointer; color: var(--secondary-text-color); font-size:.85em; text-transform:uppercase; letter-spacing:.05em; font-weight:600; }
        .version { border-left:3px solid var(--divider-color); padding:4px 0 4px 10px; margin-top:8px; }
        .version.en_cours { border-left-color: var(--primary-color); }
        .version.prevue { border-left-color:#f57c00; }
        .v-tete { display:flex; justify-content:space-between; }
        .statut { font-size:.8em; color: var(--secondary-text-color); }
        .tuiles { display:grid; grid-template-columns:repeat(auto-fit, minmax(92px, 1fr)); gap:6px; }
        .tuile { background: var(--secondary-background-color, #f5f5f5); border-radius:10px; padding:6px 8px; display:flex; flex-direction:column; }
        .t-titre { font-size:.72em; color: var(--secondary-text-color); }
        .t-val { font-weight:700; font-size:1em; white-space:nowrap; }
        .t-kwh { font-size:.72em; color: var(--secondary-text-color); }
        .mensualite { margin-top:10px; }
        .m-ligne { display:flex; justify-content:space-between; align-items:baseline; gap:8px; margin-top:2px; }
        .m-ligne > :last-child { white-space:nowrap; }
        .m-ligne.solde { margin-top:8px; }
        .ok { color:#2e7d32; font-weight:600; }
        .dont { text-align:right; font-size:.75em; color: var(--secondary-text-color); margin-top:-2px; }
        .conseil { margin-top:4px; font-size:.85em; padding:6px 8px; border-radius:8px; background: rgba(255,152,0,.1); }
        .var { display:flex; justify-content:space-between; gap:8px; font-variant-numeric: tabular-nums; }
        .petite { --mdc-icon-size:14px; vertical-align:-2px; margin-right:4px; }
        .js-ligne { display:flex; gap:8px; }
        .js { flex:1; border:1px solid var(--divider-color); border-radius:10px; padding:6px 10px; cursor:pointer; display:flex; flex-direction:column; }
        .js.auto { cursor:default; }
        .js.special { border-color:#c62828; background:rgba(198,40,40,.08); }
        .js-titre { font-size:.75em; color: var(--secondary-text-color); }
        .js-val { font-weight:600; }
      </style>
      <ha-card>
        <div class="entete">
          <ha-icon icon="mdi:lightning-bolt"></ha-icon>
          <div class="titre">${echapper(titre || T.titreDefaut)}</div>
          <ha-icon class="reglages" icon="mdi:cog-outline" title="${T.reglages}"></ha-icon>
        </div>
        <div class="contenu">
          <div class="principal">
            <div class="prix">${euro(prix)}<span class="unite">€/kWh</span></div>
            <span class="badge" style="--c:${couleurPeriode}">${echapper(this._periode(o, a, periode, a.jour_special))}</span>
            ${badgeTempo}
            ${a.prix_bas ? `<span class="badge bas">${T.prixBas}</span>` : ""}
          </div>
          ${prochain}
          ${minmax}
          ${evolution}
          ${this._config.afficher_frise ? `<div class="section"><h4>${T.prochaines(this._config.heures)}</h4>${this._frise(o, a)}</div>` : ""}
          ${a.jours_speciaux ? `<div class="section"><h4>${T.joursSpeciaux}</h4>${this._joursSpeciaux(o, a)}</div>` : ""}
          ${a.type_offre === "dynamique" && a.previsions_disponibles === false ? `<div class="legende">${T.dynSansPrevision}</div>` : ""}
          ${estTempo && this._config.afficher_tempo ? `<div class="section"><h4>${T.couleursTempo}</h4>${this._tempo(o, a)}</div>` : ""}
          ${this._config.afficher_suivi ? this._suivi(o, a) : ""}
          ${this._config.afficher_grille ? `<div class="section"><h4>${T.grille}</h4>${this._grille(o, a)}</div>` : ""}
          ${this._config.afficher_historique ? this._historique(o, a) : ""}
        </div>
      </ha-card>`;
    this.shadowRoot.querySelector(".reglages")?.addEventListener("click", () => this._ouvrirReglages());
    this.shadowRoot.querySelector(".principal")?.addEventListener("click", () => this._plusInfo());
    this.shadowRoot.querySelector("details.historique")?.addEventListener("toggle", (ev) => {
      this._histOuvert = ev.target.open;
    });
    this.shadowRoot.querySelectorAll(".js").forEach((el) =>
      el.addEventListener("click", () => this._changerJour(el.dataset.quand))
    );
  }
}

const SCHEMA_EDITEUR = [
  {
    name: "entity",
    required: true,
    selector: { entity: { filter: [{ domain: "sensor", integration: "tarifs_electricite" }] } },
  },
  { name: "titre", selector: { text: {} } },
  {
    name: "heures",
    selector: {
      select: {
        mode: "dropdown",
        options: [
          { value: 12, label: "12 h" },
          { value: 24, label: "24 h" },
          { value: 48, label: "48 h" },
        ],
      },
    },
  },
  { name: "afficher_frise", selector: { boolean: {} } },
  { name: "afficher_tempo", selector: { boolean: {} } },
  { name: "afficher_grille", selector: { boolean: {} } },
  { name: "afficher_historique", selector: { boolean: {} } },
  { name: "afficher_suivi", selector: { boolean: {} } },
];

class TarifsElectriciteCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { heures: 24, afficher_frise: false, afficher_tempo: false, afficher_grille: false, afficher_historique: false, afficher_suivi: false, ...config };
    this._rendu();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) {
      this._form.hass = hass;
      this._form.computeLabel = (s) => TEXTES[langue(hass)].editeur[s.name] || s.name;
    }
  }

  _rendu() {
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        this._config = ev.detail.value;
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: this._config },
            bubbles: true,
            composed: true,
          })
        );
      });
      this.appendChild(this._form);
    }
    this._form.computeLabel = (s) => TEXTES[langue(this._hass)].editeur[s.name] || s.name;
    this._form.schema = SCHEMA_EDITEUR;
    this._form.data = this._config;
    if (this._hass) this._form.hass = this._hass;
  }
}

if (!customElements.get("tarifs-electricite-card")) {
  customElements.define("tarifs-electricite-card", TarifsElectriciteCard);
  customElements.define("tarifs-electricite-card-editor", TarifsElectriciteCardEditor);
  const fr = langue(null) === "fr";
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "tarifs-electricite-card",
    name: "Tarifs Électricité",
    description: fr
      ? "Prix du kWh en cours, heures pleines/creuses, week-end, jours spéciaux, Tempo, prix dynamique, consommation et factures."
      : "Current electricity price, peak/off-peak, weekends, special days, Tempo, dynamic prices, consumption and bills.",
    preview: true,
    documentationURL: "https://github.com/JVmaisGpeur/ha-tarifs-electricite",
  });
  console.info(`%c TARIFS-ELECTRICITE-CARD %c v${VERSION_CARTE} `, "background:#f57c00;color:#fff", "");
}
