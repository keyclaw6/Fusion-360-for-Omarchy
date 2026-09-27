"""Run from Fusion's Scripts dialog. Creates a new document and unique local outputs.

This supplements, and never replaces, an independent interactive review.
Camera/refresh call times are not end-to-end input latency or measured display FPS.
"""

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import statistics
import time
import traceback

import adsk.core
import adsk.fusion


def run(context):
    app = adsk.core.Application.get()
    output = Path(os.environ["LOCALAPPDATA"]) / "FusionOmarchyValidation" / datetime.now(
        timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output.mkdir(parents=True, exist_ok=False)
    result = {"application_version": app.version, "completed": False,
              "cloud_save_tested": False, "independent_acceptance": False,
              "output_directory": str(output)}
    try:
        started = time.perf_counter()
        document = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        document.name = "Omarchy validation " + output.name
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        root = design.rootComponent
        occurrence = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        component = occurrence.component
        component.name = "Mounting plate 80 x 50 mm"
        point = adsk.core.Point3D.create
        value = adsk.core.ValueInput.createByString

        sketch = component.sketches.add(component.xYConstructionPlane)
        sketch.name = "Plate outline"
        sketch.sketchCurves.sketchLines.addTwoPointRectangle(point(0, 0, 0), point(8, 5, 0))
        extrude = component.features.extrudeFeatures.addSimple(
            sketch.profiles.item(0), value("8 mm"), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        extrude.name = "Plate thickness"
        body = extrude.bodies.item(0)
        extent = adsk.fusion.DistanceExtentDefinition.cast(extrude.extentOne)
        extent.distance.expression = "10 mm"
        design.computeAll()
        assert abs(body.boundingBox.maxPoint.z - 1.0) < 1e-5, "Thickness edit did not regenerate"
        extent.distance.expression = "8 mm"
        design.computeAll()
        assert abs(body.boundingBox.maxPoint.z - 0.8) < 1e-5, "Thickness reset did not regenerate"

        holes = component.sketches.add(component.xYConstructionPlane)
        holes.name = "Four mounting holes"
        for x, y in ((1, 1), (7, 1), (1, 4), (7, 4)):
            holes.sketchCurves.sketchCircles.addByCenterRadius(point(x, y, 0), 0.4)
        profiles = adsk.core.ObjectCollection.create()
        for profile in holes.profiles:
            profiles.add(profile)
        cut = component.features.extrudeFeatures.addSimple(
            profiles, value("8 mm"), adsk.fusion.FeatureOperations.CutFeatureOperation)
        cut.name = "Through holes 8 mm"
        edges = adsk.core.ObjectCollection.create()
        for edge in body.edges:
            if not edge.startVertex or not edge.endVertex:
                continue
            a, b = edge.startVertex.geometry, edge.endVertex.geometry
            if (abs(a.z - b.z) > 0.79 and min(abs(a.x), abs(a.x - 8)) < 1e-6
                    and min(abs(a.y), abs(a.y - 5)) < 1e-6):
                edges.add(edge)
        assert edges.count == 4, "Expected four outer corner edges"
        fillet_input = component.features.filletFeatures.createInput()
        fillet_input.edgeSetInputs.addConstantRadiusEdgeSet(edges, value("2 mm"), False)
        fillet = component.features.filletFeatures.add(fillet_input)
        fillet.name = "Rounded outer corners"
        sketch.isVisible = False
        holes.isVisible = False
        assert body.isSolid and body.volume > 0

        for index in range(1, 64):
            transform = adsk.core.Matrix3D.create()
            transform.translation = adsk.core.Vector3D.create((index % 8) * 10, (index // 8) * 7, 0)
            root.occurrences.addExistingComponent(component, transform)
        design.computeAll()
        for feature in (sketch, extrude, holes, cut, fillet):
            assert feature.healthState == adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState, (
                feature.name + ": " + feature.errorOrWarningMessage)
        assert root.occurrences.count == 64, "Expected 64 plate occurrences"
        assert component.bRepBodies.count == 1 and body.isSolid, "Expected one solid master plate"
        volume = body.getPhysicalProperties(
            adsk.fusion.CalculationAccuracy.VeryHighCalculationAccuracy).volume
        expected_volume = (8 * 5 - 4 * math.pi * 0.4 ** 2
                           - 4 * (0.2 ** 2 - math.pi * 0.2 ** 2 / 4)) * 0.8
        assert abs(volume - expected_volume) < 1e-4, "Unexpected plate volume"
        result.update(occurrences=root.occurrences.count, master_body_faces=body.faces.count,
                      master_body_volume_cm3=volume, expected_volume_cm3=expected_volume,
                      feature_health_verified=True, feature_edit_verified=True,
                      construction_seconds=time.perf_counter() - started)

        viewport = app.activeViewport
        camera = viewport.camera
        camera.viewOrientation = adsk.core.ViewOrientations.IsoTopRightViewOrientation
        camera.isFitView = True
        camera.isSmoothTransition = False
        viewport.camera = camera
        viewport.fit()
        viewport.refresh()
        adsk.doEvents()
        assert viewport.saveAsImageFile(str(output / "assembly.png"), 1600, 1000)

        original = viewport.camera
        target, eye = original.target, original.eye
        dx, dy, dz = eye.x - target.x, eye.y - target.y, eye.z - target.z
        samples = []
        for step in range(90):
            angle = math.tau * step / 90
            camera = viewport.camera
            camera.eye = point(target.x + dx * math.cos(angle) - dy * math.sin(angle),
                               target.y + dx * math.sin(angle) + dy * math.cos(angle), target.z + dz)
            camera.target = target
            camera.isSmoothTransition = False
            tick = time.perf_counter()
            viewport.camera = camera
            viewport.refresh()
            adsk.doEvents()
            samples.append((time.perf_counter() - tick) * 1000)
        viewport.camera = original
        result["camera_refresh_call_ms"] = {"samples": len(samples),
            "median": statistics.median(samples), "p95": sorted(samples)[85], "maximum": max(samples)}

        exports = design.exportManager
        assert exports.execute(exports.createFusionArchiveExportOptions(str(output / "assembly.f3d")))
        assert exports.execute(exports.createSTEPExportOptions(str(output / "assembly.step")))
        for filename in ("assembly.png", "assembly.f3d", "assembly.step"):
            assert (output / filename).is_file() and (output / filename).stat().st_size > 0, filename
        result["completed"] = True
        print("Validation fixture created: 64 mounting plates.\n"
            "Local archive, STEP and report: " + str(output) + "\n"
            "Cloud save/reopen and independent interactive acceptance still need verification.")
    except Exception:
        result["error"] = traceback.format_exc()
        print("Validation stopped. See the local report: " + str(output))
        raise
    finally:
        (output / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
