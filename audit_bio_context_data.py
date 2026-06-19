#!/usr/bin/env python3
"""
Audit script to identify what bio context data exists locally vs production.

Usage:
    python3 audit_bio_context_data.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymproject.settings_local')
sys.path.insert(0, '/Users/davidmillanblanco/Desktop/app3/app/a/gymproject')

django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from hyrox.models import UserInjury, DailyRecoveryEntry, HyroxReadinessLog
from clientes.models import BitacoraDiaria


def print_header(title):
    print(f"\n{'═' * 70}")
    print(f"  {title}")
    print(f"{'═' * 70}\n")


def audit_bio_data():
    # Get user david
    try:
        usuario = User.objects.get(username='david')
        cliente = usuario.cliente_perfil
    except User.DoesNotExist:
        print("❌ No user 'david' found")
        return

    print_header(f"BIO CONTEXT DATA AUDIT — User: {usuario.username} (ID: {usuario.id})")

    # ── ACTIVE INJURIES ──
    print("1. ACTIVE INJURIES (UserInjury)")
    print("-" * 70)
    injuries = UserInjury.objects.filter(cliente=cliente, activa=True)
    if injuries.exists():
        for inj in injuries:
            print(f"  ✓ {inj.zona_afectada} — Fase: {inj.fase}, Gravedad: {inj.gravedad}")
            print(f"    Tags: {inj.tags_restringidos}")
    else:
        print("  ⚠ NO ACTIVE INJURIES")

    # ── DAILY RECOVERY ENTRIES ──
    print("\n2. DAILY RECOVERY ENTRIES (DailyRecoveryEntry) — Last 7 days")
    print("-" * 70)
    recovery_entries = DailyRecoveryEntry.objects.filter(
        lesion__cliente=cliente,
        fecha__gte=timezone.now().date() - timedelta(days=7)
    ).order_by('-fecha')

    if recovery_entries.exists():
        for entry in recovery_entries:
            print(f"  ✓ {entry.fecha} — Pain REST: {entry.dolor_reposo}, MOVEMENT: {entry.dolor_movimiento}")
            print(f"    Swelling: {entry.inflamacion_percibida}, ROM: {entry.rango_movimiento}")
    else:
        print("  ⚠ NO RECOVERY ENTRIES (last 7 days)")

    # ── BITACORA DIARIA (Daily checkins) ──
    print("\n3. BITACORA DIARIA (Check-ins) — Last 7 days")
    print("-" * 70)
    bitacora = BitacoraDiaria.objects.filter(
        cliente=cliente,
        fecha__gte=timezone.now().date() - timedelta(days=7)
    ).order_by('-fecha')

    if bitacora.exists():
        for entry in bitacora:
            print(f"  ✓ {entry.fecha} — Energía: {entry.energia_subjetiva}, Sleep: {entry.calidad_sueno}")
            print(f"    HR Reposo: {entry.fc_reposo}, HRV: {entry.hrv_ms}")
    else:
        print("  ⚠ NO CHECK-INS (last 7 days)")

    # ── HYROX READINESS LOG ──
    print("\n4. HYROX READINESS LOG — Last 7 days")
    print("-" * 70)
    try:
        # Try to get HyroxObjective for this user first
        from hyrox.models import HyroxObjective
        objective = HyroxObjective.objects.filter(usuario=usuario).first()
        if objective:
            readiness = HyroxReadinessLog.objects.filter(
                objective=objective,
                fecha__gte=timezone.now().date() - timedelta(days=7)
            ).order_by('-fecha')
            if readiness.exists():
                for log in readiness:
                    print(f"  ✓ {log.fecha} — Score: {log.score}, HRV: {log.hrv_ms}")
            else:
                print("  ⚠ NO READINESS LOGS (last 7 days)")
        else:
            print("  ⚠ NO HYROX OBJECTIVE for this user")
    except Exception as e:
        print(f"  ⚠ Error querying readiness logs: {e}")

    # ── SUMMARY ──
    print_header("SUMMARY")
    print("Data required for BIO CONTEXT to show PROTOCOLO ADAPTATIVO panel:\n")
    print(f"  Active Injury:        {'✓ YES' if injuries.exists() else '❌ NO'}")
    print(f"  Recovery Entries:     {'✓ YES' if recovery_entries.exists() else '❌ NO'}")
    print(f"  Daily Check-ins:      {'✓ YES' if bitacora.exists() else '❌ NO'}")

    print("\n✓ Panel appears if: (injury is active) OR (recovery entries exist) OR (readiness < 0.8)")
    print("✓ Volume modifier calculated from: Helms factor + pain score + phase penalty\n")

    # ── RECOMMENDATION ──
    if not (injuries.exists() or recovery_entries.exists() or bitacora.exists()):
        print("⚠️  RECOMMENDATION:")
        print("   Production likely doesn't have bio data for this user.")
        print("   Panel won't show unless user has active injury or check-ins exist.")
        print("   Create sample data or sync from local environment.\n")


if __name__ == '__main__':
    audit_bio_data()
