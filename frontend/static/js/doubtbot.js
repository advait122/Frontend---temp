import * as THREE from "/static/vendor/three/three.module.js";
import { GLTFLoader } from "/static/vendor/three/examples/jsm/loaders/GLTFLoader.js";

const launcher = document.getElementById("doubtbot-launcher");
const canvas = document.getElementById("doubtbot-canvas");
const panel = document.getElementById("doubtbot-panel");
const closeBtn = document.getElementById("doubtbot-close");
const thread = document.getElementById("doubtbot-thread");
const form = panel ? panel.querySelector(".doubtbot-form") : null;
const input = form ? form.querySelector("[data-doubtbot-input]") : null;
const keepOpenKey = "pathforge_doubtbot_open";
const panelTransitionMs = 460;

if (launcher && panel) {
    let closeTimer = null;

    function scrollToBottom() {
        if (thread) {
            thread.scrollTop = thread.scrollHeight;
        }
    }

    function resizeInput() {
        if (!input) {
            return;
        }

        input.style.height = "auto";
        input.style.height = Math.min(input.scrollHeight, 132) + "px";
    }

    function finalizeClose() {
        if (closeTimer) {
            window.clearTimeout(closeTimer);
            closeTimer = null;
        }
        panel.hidden = true;
        panel.classList.remove("is-closing");
    }

    function openPanel() {
        if (closeTimer) {
            window.clearTimeout(closeTimer);
            closeTimer = null;
        }
        panel.hidden = false;
        panel.classList.remove("is-closing");
        window.requestAnimationFrame(function () {
            panel.classList.add("is-open");
        });
        launcher.setAttribute("aria-expanded", "true");
        resizeInput();
        scrollToBottom();
        if (input) {
            window.setTimeout(function () {
                input.focus();
            }, 220);
        }
    }

    function closePanel() {
        if (panel.hidden) {
            return;
        }
        panel.classList.remove("is-open");
        panel.classList.add("is-closing");
        launcher.setAttribute("aria-expanded", "false");
        if (closeTimer) {
            window.clearTimeout(closeTimer);
        }
        closeTimer = window.setTimeout(finalizeClose, panelTransitionMs);
    }

    launcher.addEventListener("click", function (event) {
        event.stopPropagation();
        if (panel.hidden) {
            openPanel();
        } else {
            closePanel();
        }
    });

    if (closeBtn) {
        closeBtn.addEventListener("click", function (event) {
            event.stopPropagation();
            closePanel();
        });
    }

    panel.addEventListener("click", function (event) {
        event.stopPropagation();
    });

    panel.addEventListener("transitionend", function (event) {
        if (event.target !== panel) {
            return;
        }
        if (panel.classList.contains("is-closing")) {
            finalizeClose();
        }
    });

    document.addEventListener("click", function () {
        if (!panel.hidden) {
            closePanel();
        }
    });

    if (form) {
        form.addEventListener("submit", function () {
            window.sessionStorage.setItem(keepOpenKey, "1");
        });
    }

    if (input) {
        resizeInput();
        input.addEventListener("input", resizeInput);
    }

    if (window.sessionStorage.getItem(keepOpenKey) === "1" || window.location.hash === "#doubtbot-widget") {
        openPanel();
        window.sessionStorage.removeItem(keepOpenKey);
    }
}

if (launcher && panel && canvas) {

const modelUrl = launcher.dataset.modelUrl || "/static/models/genkub_greeting_robot.glb";
const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
    powerPreference: "low-power",
});

renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.08;
renderer.setClearColor(0x000000, 0);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(24, 1, 0.01, 100);

scene.add(new THREE.AmbientLight(0xffffff, 0.16));
scene.add(new THREE.HemisphereLight(0xeef4ff, 0x1b2230, 0.7));

const mainLight = new THREE.DirectionalLight(0xfff4ee, 2.6);
mainLight.position.set(-2.8, 5.9, 7.4);
scene.add(mainLight);

const fillLight = new THREE.DirectionalLight(0xcfe1ff, 0.72);
fillLight.position.set(5.6, 2.2, 6.2);
scene.add(fillLight);

const rimLight = new THREE.DirectionalLight(0xffb4c5, 1.18);
rimLight.position.set(4.6, 3.1, -4.2);
scene.add(rimLight);

const frontLight = new THREE.PointLight(0xffffff, 0.62, 18, 2);
frontLight.position.set(0.15, 2.1, 5.3);
scene.add(frontLight);

const blushLight = new THREE.PointLight(0xff9bb8, 0.42, 14, 2);
blushLight.position.set(-2.1, 2.7, 4.8);
scene.add(blushLight);

const coolLight = new THREE.PointLight(0x8fcbff, 0.34, 14, 2);
coolLight.position.set(2.4, 2.1, 4.4);
scene.add(coolLight);

const pmremGenerator = new THREE.PMREMGenerator(renderer);
const envScene = new THREE.Scene();
const envRoom = new THREE.Mesh(
    new THREE.BoxGeometry(14, 14, 14),
    new THREE.MeshStandardMaterial({
        color: 0x161c27,
        roughness: 1,
        metalness: 0,
        side: THREE.BackSide,
    })
);

envScene.add(envRoom);

function addEnvCard(color, width, height, position, rotation) {
    const card = new THREE.Mesh(
        new THREE.PlaneGeometry(width, height),
        new THREE.MeshBasicMaterial({ color: color })
    );
    card.position.copy(position);
    card.rotation.set(rotation.x, rotation.y, rotation.z);
    envScene.add(card);
}

addEnvCard(0x4b5059, 5.8, 4.9, new THREE.Vector3(0, 2.3, 4.4), new THREE.Euler(0, Math.PI, 0));
addEnvCard(0x5b3340, 4.6, 3.8, new THREE.Vector3(-4.6, 1.8, 1.6), new THREE.Euler(0, 0.88, 0));
addEnvCard(0x33455a, 4.4, 3.6, new THREE.Vector3(4.4, 1.6, 1.7), new THREE.Euler(0, -0.84, 0));
addEnvCard(0x70757e, 6.6, 6.2, new THREE.Vector3(0, 4.8, 0), new THREE.Euler(Math.PI * 0.5, 0, 0));
addEnvCard(0x2f3542, 5.4, 2.2, new THREE.Vector3(0, -2.8, 0.8), new THREE.Euler(-Math.PI * 0.42, 0, 0));

scene.environment = pmremGenerator.fromScene(envScene, 0.05).texture;
pmremGenerator.dispose();

const rig = new THREE.Group();
const floatGroup = new THREE.Group();
const modelRoot = new THREE.Group();
floatGroup.add(modelRoot);
rig.add(floatGroup);
scene.add(rig);

const target = { rotateX: 0, rotateY: 0 };
const current = { rotateX: 0, rotateY: 0 };
const baseRotation = {
    x: -0.08,
    y: Math.PI * 1.52,
    z: 0.03,
};

const loader = new GLTFLoader();
const clock = new THREE.Clock();
let robotLoaded = false;
let neckNode = null;
let headNode = null;
let eyesNode = null;
let mouthNode = null;
let neckBaseRotation = null;
let headBaseRotation = null;
let eyesBaseRotation = null;
let mouthBaseRotation = null;

function resizeRenderer() {
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height));

    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
}

function normalizeModel(object) {
    const box = new THREE.Box3().setFromObject(object);
    const size = box.getSize(new THREE.Vector3());
    const desiredHeight = 1.51;
    const scale = size.y > 0 ? desiredHeight / size.y : 1;

    object.scale.setScalar(scale);

    const scaledBox = new THREE.Box3().setFromObject(object);
    const scaledSize = scaledBox.getSize(new THREE.Vector3());
    const scaledCenter = scaledBox.getCenter(new THREE.Vector3());
    const sphere = scaledBox.getBoundingSphere(new THREE.Sphere());
    const distance = Math.max(5.45, sphere.radius * 4.24);

    object.position.x -= scaledCenter.x;
    object.position.y -= scaledBox.min.y;
    object.position.z -= scaledCenter.z;

    modelRoot.rotation.set(baseRotation.x, baseRotation.y, baseRotation.z);
    modelRoot.position.set(-0.02, 0, 0);

    camera.position.set(0.03, scaledSize.y * 0.67, distance);
    camera.lookAt(0, scaledSize.y * 0.46, 0.02);
    camera.near = Math.max(0.01, distance / 60);
    camera.far = distance * 12;
    camera.updateProjectionMatrix();
}

function applyMeshStyle(material, style) {
    material.color.set(style.color);
    material.metalness = style.metalness;
    material.roughness = style.roughness;
    material.toneMapped = style.toneMapped !== undefined ? style.toneMapped : true;
    if ("envMapIntensity" in material) {
        material.envMapIntensity = style.envMapIntensity;
    }
    if ("clearcoat" in material) {
        material.clearcoat = style.clearcoat;
    }
    if ("clearcoatRoughness" in material) {
        material.clearcoatRoughness = style.clearcoatRoughness;
    }
    if ("emissive" in material) {
        material.emissive.set(style.emissive || 0x000000);
        material.emissiveIntensity = style.emissiveIntensity || 0;
    }
    material.needsUpdate = true;
}

function createGlowMaterial(color) {
    const material = new THREE.MeshBasicMaterial({ color: color });
    material.toneMapped = false;
    return material;
}

const shellStyle = {
    color: 0x747b86,
    metalness: 0.04,
    roughness: 0.18,
    envMapIntensity: 0.6,
    clearcoat: 1,
    clearcoatRoughness: 0.06,
    emissive: 0x000000,
    emissiveIntensity: 0,
    toneMapped: true,
};

const armStyle = {
    color: 0x080a0d,
    metalness: 0.02,
    roughness: 0.16,
    envMapIntensity: 0.4,
    clearcoat: 0.94,
    clearcoatRoughness: 0.07,
    emissive: 0x000000,
    emissiveIntensity: 0,
    toneMapped: true,
};

const handStyle = {
    color: 0x06080b,
    metalness: 0.02,
    roughness: 0.2,
    envMapIntensity: 0.34,
    clearcoat: 0.9,
    clearcoatRoughness: 0.08,
    emissive: 0x000000,
    emissiveIntensity: 0,
    toneMapped: true,
};

const screenStyle = {
    color: 0x050608,
    metalness: 0.02,
    roughness: 0.04,
    envMapIntensity: 0.18,
    clearcoat: 1,
    clearcoatRoughness: 0.02,
    emissive: 0x000000,
    emissiveIntensity: 0,
    toneMapped: true,
};

const glowWhiteStyle = {
    color: 0xffffff,
    metalness: 0,
    roughness: 0.06,
    envMapIntensity: 0.08,
    clearcoat: 0.16,
    clearcoatRoughness: 0.08,
    emissive: 0xffffff,
    emissiveIntensity: 2.8,
    toneMapped: false,
};

loader.load(
    modelUrl,
    function (gltf) {
        const robot = gltf.scene;

        robot.traverse(function (child) {
            if (child.isLight) {
                child.visible = false;
                return;
            }

            if (!child.isMesh || !child.material) {
                return;
            }

            child.castShadow = false;
            child.receiveShadow = false;
            child.frustumCulled = false;

            const meshName = ((child.name || child.parent?.name || "")).toLowerCase();
            let materials = (Array.isArray(child.material) ? child.material : [child.material]).map(function (material) {
                return material.clone();
            });

            if (meshName === "ears" || meshName.includes("body circle_2")) {
                materials = materials.map(function () {
                    return createGlowMaterial(0xffffff);
                });
                child.material = Array.isArray(child.material) ? materials : materials[0];
                return;
            }

            materials.forEach(function (material) {
                if (meshName.includes("body circle_1")) {
                    applyMeshStyle(material, screenStyle);
                } else if (meshName.includes("eyes") || meshName.includes("mouth")) {
                    applyMeshStyle(material, glowWhiteStyle);
                } else if (meshName.includes("cylinder")) {
                    applyMeshStyle(material, screenStyle);
                } else if (meshName.includes("head_2")) {
                    applyMeshStyle(material, screenStyle);
                } else if (meshName.includes("arm_") || meshName.includes("forearm") || meshName.includes("shoulder")) {
                    applyMeshStyle(material, armStyle);
                } else if (meshName.includes("hand")) {
                    applyMeshStyle(material, handStyle);
                } else {
                    applyMeshStyle(material, shellStyle);
                }
            });

            child.material = Array.isArray(child.material) ? materials : materials[0];
        });

        neckNode = robot.getObjectByName("Neck");
        headNode = robot.getObjectByName("Head");
        eyesNode = robot.getObjectByName("Eyes Move");
        mouthNode = robot.getObjectByName("Mouth Move 2");
        neckBaseRotation = neckNode ? neckNode.rotation.clone() : null;
        headBaseRotation = headNode ? headNode.rotation.clone() : null;
        eyesBaseRotation = eyesNode ? eyesNode.rotation.clone() : null;
        mouthBaseRotation = mouthNode ? mouthNode.rotation.clone() : null;

        modelRoot.add(robot);
        normalizeModel(robot);
        robotLoaded = true;
    },
    undefined,
    function () {
        launcher.classList.add("is-model-failed");
    }
);

function updateTarget(event) {
    const rect = launcher.getBoundingClientRect();
    const centerX = rect.left + (rect.width * 0.5);
    const centerY = rect.top + (rect.height * 0.38);
    const dx = THREE.MathUtils.clamp((event.clientX - centerX) / Math.max(window.innerWidth * 0.42, 420), -1, 1);
    const dy = THREE.MathUtils.clamp((event.clientY - centerY) / Math.max(window.innerHeight * 0.38, 300), -1, 1);

    target.rotateY = dx * 1.12;
    target.rotateX = dy * 0.62;
}

window.addEventListener("mousemove", updateTarget, { passive: true });
window.addEventListener("resize", resizeRenderer);
document.addEventListener("mouseleave", function () {
    target.rotateX = 0;
    target.rotateY = 0;
});

resizeRenderer();

function animate() {
    const delta = clock.getDelta();
    const elapsed = clock.elapsedTime;

    current.rotateX = THREE.MathUtils.damp(current.rotateX, target.rotateX, 4.9, delta);
    current.rotateY = THREE.MathUtils.damp(current.rotateY, target.rotateY, 4.6, delta);

    rig.rotation.x = Math.sin(elapsed * 1.04) * 0.02;
    rig.rotation.y = (current.rotateY * 0.55) + Math.sin(elapsed * 0.78) * 0.08;
    rig.rotation.z = Math.sin(elapsed * 1.18) * 0.04;
    floatGroup.position.x = Math.sin(elapsed * 0.84) * 0.026;
    floatGroup.position.y = 0.03 + Math.sin(elapsed * 1.66) * 0.1;
    floatGroup.rotation.z = Math.sin(elapsed * 1.1) * 0.03;

    if (robotLoaded) {
        modelRoot.rotation.x = baseRotation.x + Math.sin(elapsed * 0.94) * 0.01;
        modelRoot.rotation.y = baseRotation.y + (current.rotateY * 0.12);
        modelRoot.rotation.z = baseRotation.z + Math.sin(elapsed * 1.22) * 0.022;

        if (neckNode && neckBaseRotation) {
            neckNode.rotation.x = neckBaseRotation.x + (current.rotateX * 0.18) + Math.sin(elapsed * 1.08) * 0.008;
            neckNode.rotation.y = neckBaseRotation.y + (current.rotateY * 0.16);
            neckNode.rotation.z = neckBaseRotation.z + Math.sin(elapsed * 1.08) * 0.01;
        }

        if (headNode && headBaseRotation) {
            headNode.rotation.x = headBaseRotation.x + (current.rotateX * 1.08) + Math.sin(elapsed * 0.94) * 0.016;
            headNode.rotation.y = headBaseRotation.y + (current.rotateY * 0.92);
            headNode.rotation.z = headBaseRotation.z + Math.sin(elapsed * 1.16) * 0.014;
        }

        if (eyesNode && eyesBaseRotation) {
            eyesNode.rotation.x = eyesBaseRotation.x + (current.rotateX * 0.16);
            eyesNode.rotation.y = eyesBaseRotation.y + (current.rotateY * 0.22);
        }

        if (mouthNode && mouthBaseRotation) {
            mouthNode.rotation.x = mouthBaseRotation.x + (current.rotateX * 0.08);
            mouthNode.rotation.y = mouthBaseRotation.y + (current.rotateY * 0.11);
        }
    }

    renderer.render(scene, camera);
    window.requestAnimationFrame(animate);
}

    window.requestAnimationFrame(animate);
}
