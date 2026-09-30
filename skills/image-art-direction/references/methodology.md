# 方法论参考

## 何时读取

仅在解释理论依据时读取。普通生成任务不需要加载本文件。

## 概念来源映射

表中标为“本 skill 工作综合”的名称是对成熟视觉实践与生成行为的操作化，不代表已有同名独立理论。

| Skill 概念 | 主要领域依据 | 在本 Skill 中的操作化 |
|---|---|---|
| Mise-en-scène | 电影研究与电影制作 | 把人物、造型、道具、空间、色彩和灯光组织为同一个视觉世界 |
| Shot Design / Previsualization | 导演与电影摄影 | 在生成前决定 blocking、景别、机位、构图和可见信息 |
| Motivated Lighting | 电影摄影与摄影布光 | 从场景中的光源推导方向、颜色、表面响应和主体分离 |
| Figure–Ground / Visual Hierarchy | 视觉感知与设计 | 区分主视觉、支撑信息和环境语境 |
| Material Definition | 摄影布光与表面反射 | 根据黑色、金属、玻璃、织物、皮肤等不同表面选择光线与描述 |
| Attribute / Spatial Binding / Numeracy | 文生图组合性研究 | 用“实体 → 属性 → 关系”降低颜色、数量和位置错配 |
| Causal Coherence | 电影摄影、物理可信度与本 skill 的工作综合 | 为关键视觉结果建立合理原因，同时允许符合媒介的低显著性氛围处理 |
| Contact / Occlusion Geometry | Blocking、遮挡关系与文生图组合性实践的操作化 | 明确接触双方、方向、受力、遮挡顺序和必须保留的边界 |
| Frame Participation | 摄影构图、cropping 与 blocking 的操作化 | 控制局部主体的画内、画外范围和进入画面的边缘 |
| Decision Closure by Salience | 本 skill 的工作综合 | 闭合高显著性分支，并把同作用的低显著性选项抽象为共同类别 |
| Minimum Sufficient Completion | Visual Hierarchy、constraint satisfaction 与本 skill 工作综合 | 只补足画面成立所需的具体性，区分 Completion、Closure 与 Invention |
| Salience-weighted Specification | Visual Hierarchy 与 Failure-aware Prompting 的综合 | 按视觉显著性和失败风险分配描述密度 |
| Positive Geometry → Negative Disambiguation | 生成实践中的操作策略 | 先定义正确几何，再排除最可能的错误解释 |
| Locked / Editable | 参考图编辑实践 | 控制参考图编辑漂移，只重新设计用户允许改变的部分 |
| Controlled Imperfection | 摄影自然主义、编辑摄影与本 skill 工作综合 | 选择符合媒介和意图的有限不完美，不把结构错误当真实感 |
| Pose Naturalism | Blocking、人物摄影、人体重心与本 skill 工作综合 | 用重心、支撑、微不对称和关节放松避免模板化摆姿 |
| Exposure Strategy | 摄影曝光与动态范围控制 | 确定曝光锚点，以及允许 clipping 或暗部下降的区域 |
| Haptic-to-Visual Translation | 材料外观、摄影布光与本 skill 工作综合 | 仅将具有稳定视觉对应的触觉语言转成粗糙度、反射、微纹理、形变和褶皱，不由触觉词自行决定颜色 |
| Framing Anchors | 摄影构图与前景组织的操作化 | 用部分裁切的空间元素建立深度与语境 |
| Aesthetic / Genre Drift Control | 生成实践与本 skill 工作综合 | 抑制与目标媒介或审美意图冲突的高概率视觉模板 |

## 核心参考

- David Bordwell、Kristin Thompson、Jeff Smith，*Film Art: An Introduction*，13th ed.，McGraw Hill，2026 release，ISBN 978-1-264-95489-6。[出版社信息](https://www.mheducation.com/highered/product/film-art-an-introduction-bordwell.html)。
- Blain Brown，*Cinematography: Theory and Practice: For Cinematographers and Directors*，4th ed.，Routledge，2022，ISBN 978-0-367-37346-7。[出版社信息](https://www.routledge.com/Cinematography-Theory-and-Practice-For-Cinematographers-and-Directors/Brown/p/book/9780367373467)。
- Steven D. Katz，*Film Directing: Shot by Shot: Visualizing from Concept to Screen*，25th Anniversary ed.，Michael Wiese Productions。[出版社信息](https://mwp.com/product/film-directing-shot-shot-25th-anniversary-edition-visualizing-concept-screen/)。
- Fil Hunter、Steven Biver、Paul Fuqua、Robin Reid，*Light — Science & Magic: An Introduction to Photographic Lighting*，6th ed.，Routledge，2021，ISBN 978-0-367-86027-1。[出版社信息](https://www.routledge.com/Light-Science--Magic-An-Introduction-to-Photographic-Lighting/Hunter-Biver-Fuqua-Reid/p/book/9780367860271)。
- Johan Wagemans et al.，*A Century of Gestalt Psychology in Visual Perception I*，*Psychological Bulletin* 138(6)，2012，DOI 10.1037/a0029333。[全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC3482144/)。
- Kaiyi Huang et al.，*T2I-CompBench / T2I-CompBench++*，arXiv:2307.06350，v3，2025。[arXiv](https://arxiv.org/abs/2307.06350)。
- Hila Chefer et al.，*Attend-and-Excite: Attention-Based Semantic Guidance for Text-to-Image Diffusion Models*，arXiv:2301.13826，2023。[arXiv](https://arxiv.org/abs/2301.13826)。
