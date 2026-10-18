<template>
  <div>
    <div class="page-header">
      <div>
        <h1>分析中心</h1>
        <p>开奖走势 · 冷热频次 · 遗漏 · 热力 · 回声 · 结伴 · 撞车 · 脉搏 · 动量 · 邻号 · 跨度 · 连号簇 · 012路 · 和值 · 奇偶 · 质合 · 区位 · 尾数 · AC值 · 和尾 · 大小 · <a href="#shengping-pulse">升平降</a> · <a href="#zhenfu-pulse">振幅</a> · <a href="#junzhi-pulse">均值</a></p>
      </div>
    </div>

    <div class="chip-row">
      <button
        v-for="(name, key) in TYPE_NAMES"
        :key="key"
        type="button"
        class="chip"
        :class="{ active: type === key }"
        @click="type = key; load()"
      >{{ name }}</button>
    </div>

    <div class="alert alert-info" v-if="data">
      <AppIcon name="info" :size="14" style="margin-top:2px;flex:none" />
      <div>
        样本 {{ data.sample_size }} 期 · 数据状态
        <strong>{{ data.data_status === 'seed' ? '示例/种子' : '混合/爬取' }}</strong>
        · {{ data.disclaimer }}
      </div>
    </div>

    <div class="card mb-4">
      <div class="card-title">
        开奖结果
        <span class="sub">{{ TYPE_NAMES[type] }} · 基本走势（开出为彩球，灰字为遗漏）</span>
      </div>
      <div v-if="drawsLoading" class="loading-line"><AppIcon name="sync" :size="15" class="spin" />加载开奖…</div>
      <TrendChart
        v-else
        :type="type"
        :draws="draws"
        v-model:periods="periods"
        :period-options="[50, 80, 120, 300]"
      />
    </div>

    <div class="mb-4">
      <div class="section-head">
        <span>开奖回声</span>
        <span class="sub">{{ echoField.digit ? '按位对照' : '号码集合对照' }} · 近 80 期 · 仅供娱乐</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>回声对照仅供娱乐，不代表下期结果；请理性购彩。</div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="echoMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="echoSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-primary" type="button" :disabled="echoLoading" @click="runEcho">
            <AppIcon v-if="echoLoading" name="sync" :size="14" class="spin" />
            {{ echoLoading ? '对照中…' : '对照' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="echoLoading" @click="fillLatestEcho">用最新开奖对照</button>
        </div>
        <p class="form-hint">
          {{ echoField.digit ? '同一位置数字相同才算重合，顺序不能打乱。' : '看号码重合了几个，先后顺序不影响。' }}
        </p>
        <p v-if="echoError" class="bet-error">{{ echoError }}</p>
        <div v-if="echoResult" class="echo-list">
          <p class="text-xs text-muted">
            样本 {{ echoResult.sample_size }} 期
            <template v-if="echoResult.echoes.length"> · {{ echoResult.echoes.length }} 条回声</template>
          </p>
          <div v-if="!echoResult.echoes.length" class="empty">
            <div class="empty-title">没有重合</div>
            <div class="empty-desc">这注在样本里没有和历史开奖撞上的号码</div>
          </div>
          <div v-for="row in echoResult.echoes" :key="row.issue" class="echo-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span class="mono">第 {{ row.issue }} 期</span>
                <span v-if="row.draw_date">{{ row.draw_date }}</span>
                <span v-if="row.exact_match" class="source-badge">完全重合</span>
              </div>
              <NumberBalls
                :numbers="{ main: row.main, special: row.special }"
                :type="type"
                :marks="echoMarks(row)"
                size="sm"
              />
            </div>
            <div class="echo-score">
              <div class="echo-score-num">{{ row.score }}</div>
              <div class="text-xs text-muted">主号 {{ row.main_shared }}<template v-if="showSpecialShare"> · 特别 {{ row.special_shared }}</template></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <div class="section-head">
        <span>号码结伴</span>
        <span class="sub">主号共现 · 近 {{ affinityWindow }} 期 · 仅供娱乐</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ affinity?.disclaimer || '号码结伴只看近期开奖里哪些号码一起出现，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">{{ affinityDigit ? '看某个数字' : '看某个号' }}</label>
            <input
              v-model="affinitySeed"
              class="form-input mono"
              :placeholder="affinityDigit ? '如 7' : '如 07'"
              @keydown.enter="loadAffinity"
            />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-primary" type="button" :disabled="affinityLoading" @click="loadAffinity">
            <AppIcon v-if="affinityLoading" name="sync" :size="14" class="spin" />
            {{ affinityLoading ? '统计中…' : '查看结伴' }}
          </button>
          <button
            v-if="affinitySeed.trim()"
            class="btn btn-ghost"
            type="button"
            :disabled="affinityLoading"
            @click="clearAffinitySeed"
          >看整体</button>
        </div>
        <p class="form-hint">{{ affinityHint }}</p>
        <p v-if="affinityError" class="bet-error">{{ affinityError }}</p>
        <div v-if="affinityLoading && !affinity" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计结伴…
        </div>
        <div v-else-if="affinity" class="affinity-list">
          <p class="text-xs text-muted">
            样本 {{ affinity.sample_size }} 期
            <template v-if="affinity.seed"> · 正在看 {{ affinity.seed }}</template>
            <template v-if="affinity.mode === 'digit'"> · 不同位置</template>
          </p>
          <div v-if="!affinity.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有主号样本后，这里会列出经常一起出现的号码</div>
          </div>
          <template v-else>
            <div v-if="affinity.seed" class="affinity-block">
              <div class="card-title">{{ affinityDigit ? '这个数字的结伴' : '这个号的结伴' }}
                <span class="sub">出现时对方也在</span>
              </div>
              <div v-for="group in affinity.companions" :key="affinityKey(group)" class="affinity-group">
                <div v-if="!group.appearances" class="empty">
                  <div class="empty-title">样本里没有这个号</div>
                  <div class="empty-desc">换一个号码，或看看下面经常一起出现的组合</div>
                </div>
                <template v-else>
                  <div class="affinity-side affinity-anchor">
                    <span v-if="group.position_label" class="pos-label">{{ group.position_label }}</span>
                    <NumberBalls
                      interactive
                      :numbers="{ main: [group.n] }"
                      :type="type"
                      size="sm"
                      @pick="pickAffinitySeed"
                    />
                    <span class="text-xs text-muted">出现 {{ group.appearances }} 次</span>
                  </div>
                  <div v-if="!group.companions.length" class="text-xs text-muted">没有其他号码和它一起出现</div>
                  <div v-for="item in group.companions" :key="affinityKey(item)" class="affinity-companion">
                    <div class="affinity-side">
                      <span v-if="item.position_label" class="pos-label">{{ item.position_label }}</span>
                      <NumberBalls
                        interactive
                        :numbers="{ main: [item.n] }"
                        :type="type"
                        size="sm"
                        @pick="pickAffinitySeed"
                      />
                    </div>
                    <div class="affinity-note" title="这个号出现的期里，对方也出现的比例">{{ item.count }} 次 · 同行 {{ affinityRate(item.rate) }}</div>
                  </div>
                </template>
              </div>
            </div>

            <div v-else-if="affinityGroups.length" class="affinity-block">
              <div class="card-title">热号结伴 <span class="sub">出现时对方也在 · 点号码可只看它</span></div>
              <div v-for="group in affinityGroups" :key="affinityKey(group)">
                <div class="affinity-side affinity-anchor">
                  <span v-if="group.position_label" class="pos-label">{{ group.position_label }}</span>
                  <NumberBalls
                    interactive
                    :numbers="{ main: [group.n] }"
                    :type="type"
                    size="sm"
                    @pick="pickAffinitySeed"
                  />
                  <span class="text-xs text-muted">出现 {{ group.appearances }} 次</span>
                </div>
                <div v-for="item in group.companions" :key="affinityKey(group) + '-' + affinityKey(item)" class="affinity-companion">
                  <div class="affinity-side">
                    <span v-if="item.position_label" class="pos-label">{{ item.position_label }}</span>
                    <NumberBalls
                      interactive
                      :numbers="{ main: [item.n] }"
                      :type="type"
                      size="sm"
                      @pick="pickAffinitySeed"
                    />
                  </div>
                  <div class="affinity-note" title="这个号出现的期里，对方也出现的比例">{{ item.count }} 次 · 同行 {{ affinityRate(item.rate) }}</div>
                </div>
              </div>
            </div>

            <div class="affinity-block">
              <div class="card-title">常一起出现 <span class="sub">占全部样本</span></div>
              <div v-if="!affinity.top_pairs.length" class="empty">
                <div class="empty-title">还没有成对的号码</div>
                <div class="empty-desc">样本里的主号太少，凑不成一对</div>
              </div>
              <div
                v-for="pair in affinity.top_pairs"
                :key="pairKey(pair)"
                class="affinity-pair"
              >
                <div class="affinity-side">
                  <span v-if="pair.label_a" class="pos-label">{{ pair.label_a }}</span>
                  <NumberBalls
                    interactive
                    :numbers="{ main: [pair.a] }"
                    :type="type"
                    size="sm"
                    @pick="pickAffinitySeed"
                  />
                  <span class="plus">+</span>
                  <span v-if="pair.label_b" class="pos-label">{{ pair.label_b }}</span>
                  <NumberBalls
                    interactive
                    :numbers="{ main: [pair.b] }"
                    :type="type"
                    size="sm"
                    @pick="pickAffinitySeed"
                  />
                </div>
                <div class="affinity-note" title="两号出现在同一期的次数，占样本期数">{{ pair.count }} 次 · 占 {{ affinityRate(pair.rate) }}</div>
              </div>
            </div>

            <div v-if="affinity.special && affinity.special.top_pairs.length" class="affinity-block">
              <div class="card-title">{{ affinity.special.label }} <span class="sub">和主号一起出现，不计入上面的结伴</span></div>
              <div v-for="row in affinity.special.top_pairs.slice(0, 4)" :key="specialKey(row)" class="affinity-companion">
                <div class="affinity-side">
                  <span v-if="row.position_label" class="pos-label">{{ row.position_label }}</span>
                  <NumberBalls
                    :numbers="{ main: [row.main || row.n], special: [row.special] }"
                    :type="type"
                    size="sm"
                  />
                </div>
                <div class="affinity-note">{{ row.count }} 次 · 占 {{ affinityRate(row.rate) }}</div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <div class="section-head">
        <span>号码撞车</span>
        <span class="sub">{{ collisionField.digit ? '按位对照' : '号码集合对照' }} · 最多 20 注 · 仅供娱乐</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ collisionResult?.disclaimer || '预测/分析仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-primary" type="button" :disabled="collisionLoading" @click="runCollision(false)">
            <AppIcon v-if="collisionLoading" name="sync" :size="14" class="spin" />
            {{ collisionLoading ? '对照中…' : '看撞车' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="collisionLoading" @click="runCollision(true)">用购彩记录</button>
          <button class="btn btn-ghost" type="button" @click="toggleCollisionPad">{{ collisionUsePad ? '改用输入' : '点选录入' }}</button>
        </div>
        <p class="form-hint">
          {{ collisionField.digit ? '同一位置数字相同才算撞号，顺序不能打乱。' : '主号看选重了几个，特别号单独算，先后顺序不影响。' }}
        </p>

        <div v-for="(ticket, index) in collisionTickets" :key="ticket.key" class="collision-ticket">
          <div class="collision-ticket-head">
            <span>第 {{ index + 1 }} 注</span>
            <button
              v-if="collisionTickets.length > 2"
              class="text-btn"
              type="button"
              @click="removeCollisionTicket(index)"
            >删除</button>
          </div>
          <template v-if="collisionUsePad && collisionField.digit">
            <div class="pos-inputs">
              <div v-for="(label, pos) in collisionField.positions" :key="label" class="form-group">
                <label class="form-label">{{ label }}</label>
                <NumberPad
                  :from="0"
                  :to="collisionField.hi"
                  :pad="1"
                  :color="type === 'qxc' ? 'purple' : 'green'"
                  :max="1"
                  :selected="ticket.digits[pos] ? [ticket.digits[pos]] : []"
                  @update:selected="setCollisionDigit(ticket, pos, $event)"
                />
              </div>
              <div v-if="collisionField.special" class="form-group">
                <label class="form-label">{{ collisionField.special.label }}</label>
                <NumberPad
                  :from="collisionField.special.from"
                  :to="collisionField.special.to"
                  :pad="1"
                  :color="collisionField.special.color"
                  :max="1"
                  :selected="splitNums(ticket.specialText).slice(0, 1)"
                  @update:selected="ticket.specialText = ($event[0] || '')"
                />
              </div>
            </div>
          </template>
          <template v-else-if="collisionUsePad">
            <div class="form-group">
              <label class="form-label">{{ collisionField.main.label }}</label>
              <NumberPad
                :from="collisionField.main.from"
                :to="collisionField.main.to"
                :pad="collisionField.main.pad"
                :color="collisionField.main.color"
                :max="collisionField.main.max"
                :selected="splitNums(ticket.mainText)"
                @update:selected="ticket.mainText = $event.join(' ')"
              />
            </div>
            <div v-if="collisionField.special" class="form-group">
              <label class="form-label">{{ collisionField.special.label }}</label>
              <NumberPad
                :from="collisionField.special.from"
                :to="collisionField.special.to"
                :pad="collisionField.special.pad"
                :color="collisionField.special.color"
                :max="collisionField.special.max"
                :selected="splitNums(ticket.specialText)"
                @update:selected="ticket.specialText = $event.join(' ')"
              />
            </div>
          </template>
          <div v-else class="form-row">
            <div class="form-group">
              <label class="form-label">{{ collisionField.digit ? '号码' : collisionField.main.label }}</label>
              <input v-model="ticket.mainText" class="form-input mono" :placeholder="echoField.main" />
            </div>
            <div v-if="collisionField.special || echoField.specialLabel" class="form-group">
              <label class="form-label">{{ collisionField.special?.label || echoField.specialLabel }}</label>
              <input v-model="ticket.specialText" class="form-input mono" :placeholder="echoField.special" />
            </div>
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="collisionTickets.length >= 20" @click="addCollisionTicket">再加一注</button>
        </div>
        <div class="form-group collision-paste">
          <label class="form-label">粘贴多注 <span class="sub">一行一注，特别号用 + 隔开</span></label>
          <textarea v-model="collisionPaste" class="form-textarea mono" rows="3" placeholder="01 02 03 04 05 06 + 07" />
          <button class="btn btn-ghost" type="button" :disabled="collisionLoading" @click="applyCollisionPaste">解析粘贴</button>
        </div>
        <p v-if="collisionError" class="bet-error">{{ collisionError }}</p>

        <div v-if="collisionResult" class="collision-list">
          <p class="text-xs text-muted">
            {{ collisionScope(collisionResult) }}
            <template v-if="collisionResult.ticket_count"> · {{ collisionResult.summary }}</template>
          </p>
          <div v-if="collisionResult.message" class="empty">
            <div class="empty-title">记录不够</div>
            <div class="empty-desc">{{ collisionResult.message }}</div>
          </div>
          <template v-else>
            <div class="collision-coverage">
              <div>
                <div class="stat-label">主号覆盖</div>
                <div class="stat-value">{{ collisionResult.unique_coverage.covered }} / {{ collisionResult.unique_coverage.pool }}</div>
              </div>
              <div>
                <div class="stat-label">撞号</div>
                <div class="stat-value">{{ collisionMainHits.length }}</div>
              </div>
            </div>
            <div class="card-title">撞号 <span class="sub">出现在 2 注及以上，圈越重重复越多</span></div>
            <div v-if="!collisionMainHits.length && !collisionSpecialHits.length" class="empty">
              <div class="empty-title">没有撞号</div>
              <div class="empty-desc">这几注的号码是拉开的</div>
            </div>
            <template v-else-if="collisionResult.mode === 'digit'">
              <div v-for="hit in collisionMainHits" :key="hit.position + '-' + hit.n" class="collision-hit">
                <span class="pos-label">{{ hit.position_label }}</span>
                <NumberBalls :numbers="{ main: [hit.n] }" :type="type" :marks="{ main: [hit.count] }" size="sm" />
                <span class="text-xs text-muted">{{ hit.count }} 注</span>
              </div>
            </template>
            <NumberBalls
              v-else
              :numbers="{ main: collisionMainHits.map((hit) => hit.n), special: collisionSpecialHits.map((hit) => hit.n) }"
              :type="type"
              :marks="{ main: collisionMainHits.map((hit) => hit.count), special: collisionSpecialHits.map((hit) => hit.count) }"
              size="sm"
            />
            <div v-if="collisionResult.mode === 'digit' && collisionSpecialHits.length" class="mt-3">
              <div class="card-title">{{ collisionField.special?.label || '特别号' }} <span class="sub">不计入上面的同位撞号</span></div>
              <div v-for="hit in collisionSpecialHits" :key="'s' + hit.n" class="collision-hit">
                <span class="ball sm crash" :class="[ballClass(type, 'special'), hit.count >= 4 ? 'crash-3' : hit.count >= 3 ? 'crash-2' : 'crash-1']">{{ hit.n }}</span>
                <span class="text-xs text-muted">{{ hit.count }} 注</span>
              </div>
            </div>

            <div class="card-title mt-3">各注</div>
            <div v-for="ticket in collisionResult.tickets" :key="ticket.index" class="echo-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>第 {{ ticket.index }} 注</span>
                  <span v-if="ticket.issue" class="mono">{{ ticket.issue }}</span>
                </div>
                <NumberBalls :numbers="collisionNumbers(ticket)" :type="type" :marks="collisionMarks(ticket)" size="sm" />
              </div>
            </div>

            <div class="card-title mt-3">两两对照</div>
            <div class="table-wrap table-wrap-plain">
              <table>
                <thead><tr><th>两注</th><th>撞上的号</th><th>说明</th></tr></thead>
                <tbody>
                  <tr v-for="pair in collisionResult.pairs" :key="pair.left + '-' + pair.right">
                    <td class="mono">{{ pair.left }} × {{ pair.right }}</td>
                    <td>
                      <span v-if="!pair.overlap_count && !pair.special_overlap_count" class="text-xs text-muted">没有撞号</span>
                      <template v-else>
                        <span v-for="(n, i) in pair.overlapping.main" :key="'m' + i" class="collision-hit">
                          <span v-if="pair.overlapping.positions?.length" class="pos-label">{{ collisionPosLabel(pair.overlapping.positions[i]) }}</span>
                          <NumberBalls :numbers="{ main: [n] }" :type="type" :marks="{ main: [Math.max(pair.overlap_count, 2)] }" size="sm" />
                        </span>
                        <span v-for="n in pair.overlapping.special" :key="'s' + n" class="collision-hit">
                          <span class="pos-label">{{ collisionField.special?.label || '特别' }}</span>
                          <span class="ball sm crash crash-1" :class="ballClass(type, 'special')">{{ n }}</span>
                        </span>
                      </template>
                    </td>
                    <td>{{ pair.waste_hint }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-if="collisionResult.mode === 'set'" class="mt-3">
              <div class="card-title">没覆盖到的号 <span class="sub">主号池里这几注都没选{{ collisionResult.holes.length >= 24 ? '，这里最多 24 个' : '' }}</span></div>
              <div v-if="!collisionResult.holes.length" class="empty">
                <div class="empty-title">主号都覆盖到了</div>
              </div>
              <div v-else class="balls">
                <span v-for="n in collisionResult.holes" :key="n" class="ball ghost sm">{{ n }}</span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <div class="section-head">
        <span>重号脉搏</span>
        <span class="sub">相邻两期 · 重号与新号 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ repeatPulse?.disclaimer || '重号脉搏只看相邻两期有没有把号码留下来，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="repeatMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="repeatSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-primary" type="button" :disabled="repeatLoading" @click="runRepeat">
            <AppIcon v-if="repeatLoading" name="sync" :size="14" class="spin" />
            {{ repeatLoading ? '对照中…' : '看这注' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="repeatLoading" @click="fillLatestRepeat">对照最新开奖</button>
        </div>
        <p class="form-hint">{{ repeatHint }}</p>
        <p v-if="repeatError" class="bet-error">{{ repeatError }}</p>

        <div v-if="repeatPulseLoading && !repeatPulse" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计脉搏…
        </div>
        <div v-else-if="repeatPulse" class="repeat-list">
          <p class="text-xs text-muted">
            样本 {{ repeatPulse.sample_size }} 期 · {{ repeatPulse.pair_count }} 次交接
            · 平均 {{ repeatStat(repeatPulse.mean) }} · 中位 {{ repeatStat(repeatPulse.median) }} · 最多 {{ repeatStat(repeatPulse.max) }}
          </p>
          <div v-if="repeatPulse.latest_draw" class="repeat-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ repeatPulse.latest_draw.issue }} 期</span>
              </div>
              <NumberBalls :numbers="repeatPulse.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!repeatPulse.pair_count" class="empty">
            <div class="empty-title">还没有相邻开奖</div>
            <div class="empty-desc">看不出重号脉搏。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">重号分布 <span class="sub">相邻两期主号重了几个，特别号不计入</span></div>
            <div class="repeat-bars">
              <div v-for="bucket in repeatPulse.distribution" :key="bucket.overlap" class="repeat-bar">
                <span class="mono">{{ bucket.overlap }}</span>
                <span class="repeat-bar-track">
                  <span class="repeat-bar-fill" :style="{ width: repeatBarWidth(bucket.count) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <div class="card-title mt-3">最近交接 <span class="sub">较早一期留下的号亮着，新号变淡</span></div>
            <div v-for="pair in repeatRecent" :key="pair.issue_from + '-' + pair.issue_to" class="repeat-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span class="mono">{{ pair.issue_from }} → {{ pair.issue_to }}</span>
                  <span v-if="pair.special_overlap">特别号重了 {{ pair.special_overlap }} 个，不计入主号</span>
                </div>
                <NumberBalls :numbers="repeatPairNumbers(pair)" :type="type" :marks="repeatPairMarks(pair)" size="sm" />
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ pair.overlap }}</div>
                <div class="text-xs text-muted">重号</div>
              </div>
            </div>
          </template>

          <div v-if="repeatScore" class="repeat-score">
            <div class="card-title">这注对照最新开奖</div>
            <div v-if="repeatScore.message" class="empty">
              <div class="empty-title">还对不上</div>
              <div class="empty-desc">{{ repeatSummary }}</div>
            </div>
            <template v-else>
              <p class="text-xs text-muted">{{ repeatSummary }}</p>
              <div class="repeat-row">
                <div class="echo-draw">
                  <div class="echo-meta"><span>这注</span><span>亮圈是重号，变淡的是新号</span></div>
                  <NumberBalls :numbers="repeatScoreView.numbers" :type="type" :marks="repeatScoreView.marks" size="sm" />
                </div>
                <div class="echo-score">
                  <div class="echo-score-num">{{ repeatScore.overlap }}</div>
                  <div class="text-xs text-muted">重号</div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <div class="section-head">
        <span>冷热动量</span>
        <span class="sub">短窗对比长窗 · 升温与降温 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ momentum?.disclaimer || '冷热动量比较短窗口和长窗口的出现率，看号码是在升温还是降温，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="momentumShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="momentumLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="momentumMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="momentumSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="momentumBoardLoading" @click="loadMomentum">
            <AppIcon v-if="momentumBoardLoading" name="sync" :size="14" class="spin" />
            {{ momentumBoardLoading ? '统计中…' : '刷新动量' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="momentumLoading" @click="runMomentum">
            <AppIcon v-if="momentumLoading" name="sync" :size="14" class="spin" />
            {{ momentumLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="momentumLoading" @click="fillLatestMomentum">用最新开奖</button>
        </div>
        <p class="form-hint">{{ momentumHint }}</p>
        <p v-if="momentumError" class="bet-error">{{ momentumError }}</p>

        <div v-if="momentumBoardLoading && !momentum" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计动量…
        </div>
        <div v-else-if="momentum" class="momentum-list">
          <p class="text-xs text-muted">
            样本 {{ momentum.sample_size }} 期 · 短窗 {{ momentum.short }} · 长窗 {{ momentum.long }}
            · 阈值 {{ momentumThreshold }} · 升温 {{ momentumRisingCount }} · 降温 {{ momentumFallingCount }}
          </p>
          <div v-if="!momentum.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有开奖后，这里会比较短窗和长窗的出现率。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
          <template v-if="momentum.mode === 'digit'">
            <div v-for="pos in momentum.positions" :key="pos.index" class="momentum-pos">
              <div class="card-title">{{ pos.label }}
                <span class="sub">升温 {{ pos.rising.length }} · 降温 {{ pos.falling.length }} · 持平 {{ pos.flat.length }}</span>
              </div>
              <div v-if="!pos.rising.length && !pos.falling.length" class="text-xs text-muted">这个位置没有明显升降</div>
              <template v-else>
                <div v-if="pos.rising.length" class="momentum-band">
                  <span class="momentum-tag">升温</span>
                  <div class="balls">
                    <span
                      v-for="n in pos.rising"
                      :key="pos.index + '-r-' + n"
                      class="ball sm rising"
                      :class="ballClass(type)"
                      :title="momentumTip(momentumStat(pos.numbers, n))"
                    >{{ n }}</span>
                  </div>
                </div>
                <div v-if="pos.falling.length" class="momentum-band">
                  <span class="momentum-tag">降温</span>
                  <div class="balls">
                    <span
                      v-for="n in pos.falling"
                      :key="pos.index + '-f-' + n"
                      class="ball ghost sm"
                      :title="momentumTip(momentumStat(pos.numbers, n))"
                    >{{ n }}</span>
                  </div>
                </div>
              </template>
            </div>
          </template>
          <template v-else>
            <div class="card-title">主号 <span class="sub">持平 {{ momentum.flat.length }} 个，不逐个展开</span></div>
            <div v-if="!momentum.rising.length && !momentum.falling.length" class="text-xs text-muted">这窗里没有明显升降</div>
            <template v-else>
              <div v-if="momentum.rising.length" class="momentum-band">
                <span class="momentum-tag">升温</span>
                <div class="balls">
                  <span
                    v-for="n in momentum.rising"
                    :key="'mr' + n"
                    class="ball sm rising"
                    :class="ballClass(type)"
                    :title="momentumTip(momentumStat(momentum.numbers, n))"
                  >{{ n }}</span>
                </div>
              </div>
              <div v-if="momentum.falling.length" class="momentum-band">
                <span class="momentum-tag">降温</span>
                <div class="balls">
                  <span
                    v-for="n in momentum.falling"
                    :key="'mf' + n"
                    class="ball ghost sm"
                    :title="momentumTip(momentumStat(momentum.numbers, n))"
                  >{{ n }}</span>
                </div>
              </div>
            </template>
          </template>

          <div v-if="momentum.special" class="momentum-pos">
            <div class="card-title">{{ momentum.special.label }} <span class="sub">单独统计，不计入主号动量</span></div>
            <div v-if="!momentum.special.rising.length && !momentum.special.falling.length" class="text-xs text-muted">特别号没有明显升降</div>
            <template v-else>
              <div v-if="momentum.special.rising.length" class="momentum-band">
                <span class="momentum-tag">升温</span>
                <div class="balls">
                  <span
                    v-for="n in momentum.special.rising"
                    :key="'spr' + n"
                    class="ball sm rising"
                    :class="ballClass(type, 'special')"
                    :title="momentumTip(momentumStat(momentum.special.numbers, n))"
                  >{{ n }}</span>
                </div>
              </div>
              <div v-if="momentum.special.falling.length" class="momentum-band">
                <span class="momentum-tag">降温</span>
                <div class="balls">
                  <span
                    v-for="n in momentum.special.falling"
                    :key="'spf' + n"
                    class="ball ghost sm"
                    :title="momentumTip(momentumStat(momentum.special.numbers, n))"
                  >{{ n }}</span>
                </div>
              </div>
            </template>
          </div>
          </template>

          <div v-if="momentumScore" class="momentum-score">
            <div class="card-title">这注的动量</div>
            <p class="text-xs text-muted">{{ momentumScoreText }}</p>
            <div class="momentum-band">
              <span class="momentum-tag">升温</span>
              <div class="balls">
                <span
                  v-for="(item, index) in momentumScore.ticket.rising"
                  :key="momentumMemberKey(item, index)"
                  class="pos-group"
                >
                  <span v-if="momentumMemberTitle(item)" class="pos-label">{{ momentumMemberTitle(item) }}</span>
                  <span class="ball sm rising" :class="ballClass(type)">{{ momentumMemberLabel(item) }}</span>
                </span>
                <span v-if="!momentumScore.ticket.rising.length" class="text-xs text-muted">没有</span>
              </div>
            </div>
            <div class="momentum-band">
              <span class="momentum-tag">降温</span>
              <div class="balls">
                <span
                  v-for="(item, index) in momentumScore.ticket.falling"
                  :key="momentumMemberKey(item, index)"
                  class="pos-group"
                >
                  <span v-if="momentumMemberTitle(item)" class="pos-label">{{ momentumMemberTitle(item) }}</span>
                  <span class="ball ghost sm">{{ momentumMemberLabel(item) }}</span>
                </span>
                <span v-if="!momentumScore.ticket.falling.length" class="text-xs text-muted">没有</span>
              </div>
            </div>
            <div class="momentum-band">
              <span class="momentum-tag">持平</span>
              <div class="balls">
                <span
                  v-for="(item, index) in momentumScore.ticket.flat"
                  :key="momentumMemberKey(item, index)"
                  class="pos-group"
                >
                  <span v-if="momentumMemberTitle(item)" class="pos-label">{{ momentumMemberTitle(item) }}</span>
                  <span class="ball ghost sm">{{ momentumMemberLabel(item) }}</span>
                </span>
                <span v-if="!momentumScore.ticket.flat.length" class="text-xs text-muted">没有</span>
              </div>
            </div>
            <div v-if="momentumSpecialScored" class="momentum-pos">
              <div class="card-title">{{ momentum.special?.label || '特别号' }} <span class="sub">这注的特别号，不计入主号分</span></div>
              <div class="momentum-band">
                <span class="momentum-tag">升温</span>
                <div class="balls">
                  <span v-for="n in momentumScore.special_ticket.rising" :key="'sr' + n" class="ball sm rising" :class="ballClass(type, 'special')">{{ n }}</span>
                  <span v-if="!momentumScore.special_ticket.rising.length" class="text-xs text-muted">没有</span>
                </div>
              </div>
              <div class="momentum-band">
                <span class="momentum-tag">降温</span>
                <div class="balls">
                  <span v-for="n in momentumScore.special_ticket.falling" :key="'sf' + n" class="ball ghost sm">{{ n }}</span>
                  <span v-if="!momentumScore.special_ticket.falling.length" class="text-xs text-muted">没有</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <div class="section-head">
        <span>邻号牵引</span>
        <span class="sub">开出之后看邻号 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ neighbor?.disclaimer || '邻号牵引看主号开出后，邻号在随后几期是否更常出现，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="neighborLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">随后（期）</label>
            <input v-model.number="neighborHorizon" class="form-input mono" type="number" min="1" max="10" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="neighborMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="neighborSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="neighborBoardLoading" @click="loadNeighbor">
            <AppIcon v-if="neighborBoardLoading" name="sync" :size="14" class="spin" />
            {{ neighborBoardLoading ? '统计中…' : '刷新牵引' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="neighborLoading" @click="runNeighbor">
            <AppIcon v-if="neighborLoading" name="sync" :size="14" class="spin" />
            {{ neighborLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="neighborLoading" @click="fillLatestNeighbor">用最新开奖</button>
        </div>
        <p class="form-hint">{{ neighborHint }}</p>
        <p v-if="neighborError" class="bet-error">{{ neighborError }}</p>

        <div v-if="neighborBoardLoading && !neighbor" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计牵引…
        </div>
        <div v-else-if="neighbor" class="neighbor-list">
          <p class="text-xs text-muted">
            样本 {{ neighbor.sample_size }} 期 · 随后 {{ neighbor.horizon }} 期
            · 边界不绕圈 · 牵出 {{ neighborPullCount }} 条
          </p>
          <div v-if="neighbor.latest_draw" class="neighbor-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ neighbor.latest_draw.issue }} 期</span>
              </div>
              <NumberBalls :numbers="neighbor.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!neighbor.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有开奖后，这里会看邻号在随后几期是否更常出现。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <template v-if="neighbor.mode === 'digit'">
              <div v-for="pos in neighbor.positions" :key="pos.index" class="neighbor-pos">
                <div class="card-title">{{ pos.label }}
                  <span class="sub">同一位置的邻号，0 和 9 不绕圈</span>
                </div>
                <div v-if="!pos.pulled.length" class="text-xs text-muted">这个位置还没有完整的随后窗口</div>
                <div v-else class="neighbor-band">
                  <span class="neighbor-tag">邻号</span>
                  <div class="balls">
                    <span v-for="edge in neighborTop(pos.pulled)" :key="pos.index + '-' + edge.source + '-' + edge.number + '-' + edge.side" class="neighbor-chip">
                      <span class="ball sm" :class="ballClass(type)" :title="neighborTip(edge)">{{ edge.number }}</span>
                      <span class="neighbor-meta">{{ edge.source }} → {{ neighborSigned(edge.lift) }}</span>
                    </span>
                  </div>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="card-title">主号 <span class="sub">牵得最勤的邻号，同期一起开出不算</span></div>
              <div v-if="!neighbor.pulled.length" class="text-xs text-muted">这窗里还没有完整的随后窗口</div>
              <div v-else class="neighbor-band">
                <span class="neighbor-tag">邻号</span>
                <div class="balls">
                  <span v-for="edge in neighborTop(neighbor.pulled)" :key="edge.source + '-' + edge.number + '-' + edge.side" class="neighbor-chip">
                    <span class="ball sm" :class="ballClass(type)" :title="neighborTip(edge)">{{ edge.number }}</span>
                    <span class="neighbor-meta">{{ edge.source }} → {{ neighborSigned(edge.lift) }}</span>
                  </span>
                </div>
              </div>
            </template>

            <div v-if="neighbor.special" class="neighbor-pos">
              <div class="card-title">{{ neighbor.special.label }} <span class="sub">单独统计，不计入主号牵引</span></div>
              <div v-if="!neighbor.special.pulled.length" class="text-xs text-muted">特别号还没有完整的随后窗口</div>
              <div v-else class="neighbor-band">
                <span class="neighbor-tag">邻号</span>
                <div class="balls">
                  <span
                    v-for="edge in neighborTop(neighbor.special.pulled)"
                    :key="'sp-' + edge.source + '-' + edge.number + '-' + edge.side"
                    class="neighbor-chip"
                  >
                    <span class="ball sm" :class="ballClass(type, 'special')" :title="neighborTip(edge)">{{ edge.number }}</span>
                    <span class="neighbor-meta">{{ edge.source }} → {{ neighborSigned(edge.lift) }}</span>
                  </span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="neighborScore" class="neighbor-score">
            <div class="card-title">这注的牵引</div>
            <p class="text-xs text-muted">{{ neighborScoreText }}</p>
            <div class="neighbor-row">
              <div class="echo-draw">
                <div class="echo-meta"><span>这注</span><span>亮圈是被牵到的号</span></div>
                <NumberBalls :numbers="neighborScoreView.numbers" :type="type" :marks="neighborScoreView.marks" size="sm" />
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ neighborScore.ticket.score }}</div>
                <div class="text-xs text-muted">牵引</div>
              </div>
            </div>
            <div v-if="neighborSpecialScored" class="neighbor-pos">
              <div class="card-title">{{ neighbor.special?.label || '特别号' }} <span class="sub">这注的特别号，不计入主号分</span></div>
              <div class="neighbor-band">
                <span class="neighbor-tag">牵引</span>
                <div class="balls">
                  <span v-for="n in neighborScore.special_ticket.pulled" :key="'nsp' + n" class="ball sm" :class="ballClass(type, 'special')">{{ n }}</span>
                  <span v-if="!neighborScore.special_ticket.pulled.length" class="text-xs text-muted">没有</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <div class="section-head">
        <span>跨度脉动</span>
        <span class="sub">短窗对比长窗 · 变宽与变窄 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ span?.disclaimer || '跨度脉动看主号跨度的历史分布，以及短窗相对长窗是变宽还是变窄，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="spanLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="spanShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="spanLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="spanMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="spanSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="spanBoardLoading" @click="loadSpan">
            <AppIcon v-if="spanBoardLoading" name="sync" :size="14" class="spin" />
            {{ spanBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="spanLoading" @click="runSpan">
            <AppIcon v-if="spanLoading" name="sync" :size="14" class="spin" />
            {{ spanLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="spanLoading" @click="fillLatestSpan">用最新开奖</button>
        </div>
        <p class="form-hint">{{ spanHint }}</p>
        <p v-if="spanError" class="bet-error">{{ spanError }}</p>

        <div v-if="spanBoardLoading && !span" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计跨度…
        </div>
        <div v-else-if="span" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ span.sample_size }} 期 · 平均 {{ spanStat(span.mean) }} · 中位 {{ spanStat(span.median) }}
            · 短窗 {{ spanStat(span.short_avg) }} · 长窗 {{ spanStat(span.long_avg) }} · 脉动 {{ spanSigned(span.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(span.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ span.short }} 期</div>
            </div>
            <div class="span-drift" :class="span.drift || 'flat'">{{ spanDriftLabel(span.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(span.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ span.long }} 期</div>
            </div>
          </div>
          <div v-if="span.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ span.latest_draw.issue }} 期</span>
                <span>跨度 {{ span.latest_draw.span }}</span>
              </div>
              <NumberBalls :numbers="span.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!span.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有开奖后，这里会看主号跨度的分布，以及短窗相对长窗是变宽还是变窄。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              跨度分布
              <span class="sub">{{ span.basis === 'digits' ? '整注各位的最大减最小' : '主号最大号减最小号' }}，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in spanBars" :key="bucket.span" class="span-bar" :class="{ 'is-current': spanCurrent(bucket.span) }">
                <span class="mono">{{ bucket.span }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, span.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <p v-if="spanBarsCollapsed" class="text-xs text-muted">跨度拉得比较开，这里只展开出现过的档。</p>
            <div v-if="span.common?.length" class="span-band">
              <span class="span-tag">常见</span>
              <div class="balls">
                <span v-for="item in span.common" :key="'c' + item.span" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="ball sm" :class="ballClass(type)">{{ item.span }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="span.special" class="span-pos">
              <div class="card-title">{{ span.special.label }} <span class="sub">至少两个特别号才算跨度，不计入主号</span></div>
              <p class="text-xs text-muted">
                {{ span.special.sample_size }} 期 · 短窗 {{ spanStat(span.special.short_avg) }} · 长窗 {{ spanStat(span.special.long_avg) }}
                · {{ spanDriftLabel(span.special.drift) }}
              </p>
              <div class="span-bars">
                <div v-for="bucket in spanSpecialBars" :key="'s' + bucket.span" class="span-bar">
                  <span class="mono">{{ bucket.span }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, span.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="spanScore" class="span-score">
            <div class="card-title">这注的跨度</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(spanScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(spanScore.ticket.alignment) }}</span>
                </div>
                <p class="text-xs text-muted">{{ spanScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ spanScore.ticket.span }}</div>
                <div class="text-xs text-muted">跨度</div>
              </div>
            </div>
            <div v-if="spanSpecialScored" class="span-pos">
              <div class="card-title">{{ span.special?.label || '特别号' }} <span class="sub">这注的特别号跨度，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ spanScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ spanScore.special_ticket.span }}</div>
                  <div class="text-xs text-muted">{{ spanRarityLabel(spanScore.special_ticket.rarity) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <div class="section-head">
        <span>连号簇脉动</span>
        <span class="sub">短窗对比长窗 · 变长与变短 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ cluster?.disclaimer || '连号簇脉动看主号连号簇最长长度的历史分布，以及短窗相对长窗是变长还是变短，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="clusterLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="clusterShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="clusterLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="clusterMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="clusterSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="clusterBoardLoading" @click="loadCluster">
            <AppIcon v-if="clusterBoardLoading" name="sync" :size="14" class="spin" />
            {{ clusterBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="clusterLoading" @click="runCluster">
            <AppIcon v-if="clusterLoading" name="sync" :size="14" class="spin" />
            {{ clusterLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="clusterLoading" @click="fillLatestCluster">用最新开奖</button>
        </div>
        <p class="form-hint">{{ clusterHint }}</p>
        <p v-if="clusterError" class="bet-error">{{ clusterError }}</p>

        <div v-if="clusterBoardLoading && !cluster" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计连号簇…
        </div>
        <div v-else-if="cluster" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ cluster.sample_size }} 期 · 平均 {{ spanStat(cluster.mean) }} · 中位 {{ spanStat(cluster.median) }}
            · 短窗 {{ spanStat(cluster.short_avg) }} · 长窗 {{ spanStat(cluster.long_avg) }} · 脉动 {{ spanSigned(cluster.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(cluster.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ cluster.short }} 期</div>
            </div>
            <div class="span-drift" :class="cluster.drift || 'flat'">{{ clusterDriftLabel(cluster.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(cluster.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ cluster.long }} 期</div>
            </div>
          </div>
          <p v-if="cluster.cluster_counts" class="text-xs text-muted">
            簇个数 · 短窗 {{ spanStat(cluster.cluster_counts.short_avg) }} · 长窗 {{ spanStat(cluster.cluster_counts.long_avg) }}
            · 脉动 {{ spanSigned(cluster.cluster_counts.pulse) }} · {{ clusterCountDriftLabel(cluster.cluster_counts.drift) }}
          </p>
          <div v-if="cluster.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ cluster.latest_draw.issue }} 期</span>
                <span>最长簇 {{ cluster.latest_draw.max_len }} · {{ cluster.latest_draw.clusters }} 个簇</span>
              </div>
              <NumberBalls :numbers="cluster.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!cluster.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有开奖后，这里会看主号连号簇有多长，以及短窗相对长窗是变长还是变短。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              最长簇分布
              <span class="sub">{{ cluster.basis === 'digits' ? '按位相邻差为 1，0 和 9 不绕圈' : '主号去重后挨在一起的最长一段' }}，没有连号记为 1，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in clusterBars" :key="bucket.max_len" class="span-bar" :class="{ 'is-current': clusterCurrent(bucket.max_len) }">
                <span class="mono">{{ bucket.max_len }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, cluster.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <p v-if="clusterBarsCollapsed" class="text-xs text-muted">最长簇拉得比较开，这里只展开出现过的档。</p>
            <div v-if="cluster.common?.length" class="span-band">
              <span class="span-tag">常见</span>
              <div class="balls">
                <span v-for="item in cluster.common" :key="'c' + item.max_len" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="ball sm" :class="ballClass(type)">{{ item.max_len }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="clusterCountBars.length" class="span-pos">
              <div class="card-title">簇个数 <span class="sub">长度至少为 2 的簇有几个，不参与上面的主脉动</span></div>
              <div class="span-bars">
                <div v-for="bucket in clusterCountBars" :key="'n' + bucket.clusters" class="span-bar">
                  <span class="mono">{{ bucket.clusters }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, cluster.cluster_counts.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
            <div v-if="cluster.special" class="span-pos">
              <div class="card-title">{{ cluster.special.label }} <span class="sub">至少两个特别号才算连号簇，不计入主号</span></div>
              <p class="text-xs text-muted">
                {{ cluster.special.sample_size }} 期 · 短窗 {{ spanStat(cluster.special.short_avg) }} · 长窗 {{ spanStat(cluster.special.long_avg) }}
                · {{ clusterDriftLabel(cluster.special.drift) }}
              </p>
              <div class="span-bars">
                <div v-for="bucket in clusterSpecialBars" :key="'s' + bucket.max_len" class="span-bar">
                  <span class="mono">{{ bucket.max_len }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, cluster.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="clusterScore" class="span-score">
            <div class="card-title">这注的连号簇</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(clusterScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(clusterScore.ticket.alignment) }}</span>
                </div>
                <p class="text-xs text-muted">{{ clusterScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ clusterScore.ticket.max_len }}</div>
                <div class="text-xs text-muted">最长簇 · {{ clusterScore.ticket.clusters }} 个</div>
              </div>
            </div>
            <div v-if="clusterSpecialScored" class="span-pos">
              <div class="card-title">{{ cluster.special?.label || '特别号' }} <span class="sub">这注的特别号连号簇，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ clusterScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ clusterScore.special_ticket.max_len }}</div>
                  <div class="text-xs text-muted">{{ spanRarityLabel(clusterScore.special_ticket.rarity) }} · {{ clusterScore.special_ticket.clusters }} 个</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <div class="section-head">
        <span>012路脉动</span>
        <span class="sub">短窗对比长窗 · 更偏与更匀 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ road?.disclaimer || '012路脉动看主号除以 3 的余数配比和路偏度，以及短窗相对长窗是更偏还是更匀，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="roadLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="roadShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="roadLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="roadMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="roadSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="roadBoardLoading" @click="loadRoad">
            <AppIcon v-if="roadBoardLoading" name="sync" :size="14" class="spin" />
            {{ roadBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="roadLoading" @click="runRoad">
            <AppIcon v-if="roadLoading" name="sync" :size="14" class="spin" />
            {{ roadLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="roadLoading" @click="fillLatestRoad">用最新开奖</button>
        </div>
        <p class="form-hint">{{ roadHint }}</p>
        <p v-if="roadError" class="bet-error">{{ roadError }}</p>

        <div v-if="roadBoardLoading && !road" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计012路…
        </div>
        <div v-else-if="road" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ road.sample_size }} 期 · 平均 {{ spanStat(road.mean) }} · 中位 {{ spanStat(road.median) }}
            · 短窗 {{ spanStat(road.short_avg) }} · 长窗 {{ spanStat(road.long_avg) }} · 脉动 {{ spanSigned(road.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(road.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ road.short }} 期</div>
            </div>
            <div class="span-drift" :class="road.drift || 'flat'">{{ roadDriftLabel(road.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(road.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ road.long }} 期</div>
            </div>
          </div>
          <div v-if="road.avg_road_counts" class="road-mix">
            <div v-for="name in ['0', '1', '2']" :key="name" class="road-mix-item">
              <span class="road-mix-label">{{ name }}路</span>
              <span class="road-mix-num">{{ spanStat(road.avg_road_counts[name]) }}</span>
            </div>
          </div>
          <div v-if="road.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ road.latest_draw.issue }} 期</span>
                <span>路偏度 {{ road.latest_draw.imbalance }} · {{ roadCountText(road.latest_draw.counts) }}</span>
              </div>
              <NumberBalls :numbers="road.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!road.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有开奖后，这里会看 0路、1路、2路各有几个，以及短窗相对长窗是更偏还是更匀。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              路偏度分布
              <span class="sub">{{ road.basis === 'digits' ? '整注各位除以 3 的余数，0 和 9 不绕圈' : '主号去重后按除以 3 的余数' }}，偏度是最多一路减去最少一路，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in roadBars" :key="bucket.imbalance" class="span-bar" :class="{ 'is-current': roadCurrent(bucket.imbalance) }">
                <span class="mono">{{ bucket.imbalance }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, road.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <p v-if="roadBarsCollapsed" class="text-xs text-muted">路偏度拉得比较开，这里只展开出现过的档。</p>
            <div v-if="road.common?.length" class="span-band">
              <span class="span-tag">常见</span>
              <div class="balls">
                <span v-for="item in road.common" :key="'c' + item.imbalance" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="ball sm" :class="ballClass(type)">{{ item.imbalance }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="road.special" class="span-pos">
              <div class="card-title">{{ road.special.label }} <span class="sub">有特别号就另计路，不计入主号</span></div>
              <p class="text-xs text-muted">
                {{ road.special.sample_size }} 期 · 短窗 {{ spanStat(road.special.short_avg) }} · 长窗 {{ spanStat(road.special.long_avg) }}
                · {{ roadDriftLabel(road.special.drift) }}
              </p>
              <div v-if="road.special.avg_road_counts" class="road-mix">
                <div v-for="name in ['0', '1', '2']" :key="'s' + name" class="road-mix-item">
                  <span class="road-mix-label">{{ name }}路</span>
                  <span class="road-mix-num">{{ spanStat(road.special.avg_road_counts[name]) }}</span>
                </div>
              </div>
              <div class="span-bars">
                <div v-for="bucket in roadSpecialBars" :key="'s' + bucket.imbalance" class="span-bar">
                  <span class="mono">{{ bucket.imbalance }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, road.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="roadScore" class="span-score">
            <div class="card-title">这注的012路</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(roadScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(roadScore.ticket.alignment) }}</span>
                  <span>{{ roadCountText(roadScore.ticket.counts) }}</span>
                </div>
                <p class="text-xs text-muted">{{ roadScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ roadScore.ticket.imbalance }}</div>
                <div class="text-xs text-muted">路偏度</div>
              </div>
            </div>
            <div v-if="roadSpecialScored" class="span-pos">
              <div class="card-title">{{ road.special?.label || '特别号' }} <span class="sub">这注的特别号路，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ roadScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ roadScore.special_ticket.imbalance }}</div>
                  <div class="text-xs text-muted">{{ spanRarityLabel(roadScore.special_ticket.rarity) }} · {{ roadCountText(roadScore.special_ticket.counts) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4" id="sum-pulse">
      <div class="section-head">
        <span>和值脉动</span>
        <span class="sub">短窗对比长窗 · 走高与走低 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ sumPulse?.disclaimer || '和值脉动看主号和值的历史分布，以及短窗相对长窗是走高还是走低，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="sumLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="sumShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="sumLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="sumMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="sumSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="sumBoardLoading" @click="loadSum">
            <AppIcon v-if="sumBoardLoading" name="sync" :size="14" class="spin" />
            {{ sumBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="sumLoading" @click="runSum">
            <AppIcon v-if="sumLoading" name="sync" :size="14" class="spin" />
            {{ sumLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="sumLoading" @click="fillLatestSum">用最新开奖</button>
        </div>
        <p class="form-hint">{{ sumHint }}</p>
        <p v-if="sumError" class="bet-error">{{ sumError }}</p>

        <div v-if="sumBoardLoading && !sumPulse" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计和值…
        </div>
        <div v-else-if="sumPulse" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ sumPulse.sample_size }} 期 · 平均 {{ spanStat(sumPulse.mean) }} · 中位 {{ spanStat(sumPulse.median) }}
            · 短窗 {{ spanStat(sumPulse.short_avg) }} · 长窗 {{ spanStat(sumPulse.long_avg) }} · 脉动 {{ spanSigned(sumPulse.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(sumPulse.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ sumPulse.short }} 期</div>
            </div>
            <div class="span-drift" :class="sumPulse.drift || 'flat'">{{ sumDriftLabel(sumPulse.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(sumPulse.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ sumPulse.long }} 期</div>
            </div>
          </div>
          <div v-if="sumPulse.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ sumPulse.latest_draw.issue }} 期</span>
                <span>和值 {{ sumPulse.latest_draw.sum }}</span>
              </div>
              <NumberBalls :numbers="sumPulse.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!sumPulse.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有开奖后，这里会看主号和值的分布，以及短窗相对长窗是走高还是走低。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              和值分布
              <span class="sub">{{ sumPulse.basis === 'digits' ? '整注各位数字相加' : '主号去重后相加' }}，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in sumBars" :key="bucket.sum" class="span-bar" :class="{ 'is-current': sumCurrent(bucket.sum) }">
                <span class="mono">{{ bucket.sum }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, sumPulse.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <p v-if="sumBarsCollapsed" class="text-xs text-muted">和值拉得比较开，这里只展开出现过的档。</p>
            <div v-if="sumPulse.common?.length" class="span-band">
              <span class="span-tag">常见</span>
              <div class="balls">
                <span v-for="item in sumPulse.common" :key="'c' + item.sum" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="ball sm" :class="ballClass(type)">{{ item.sum }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="sumPulse.special" class="span-pos">
              <div class="card-title">{{ sumPulse.special.label }} <span class="sub">至少两个特别号才算和值，不计入主号</span></div>
              <p class="text-xs text-muted">
                {{ sumPulse.special.sample_size }} 期 · 短窗 {{ spanStat(sumPulse.special.short_avg) }} · 长窗 {{ spanStat(sumPulse.special.long_avg) }}
                · {{ sumDriftLabel(sumPulse.special.drift) }}
              </p>
              <div class="span-bars">
                <div v-for="bucket in sumSpecialBars" :key="'s' + bucket.sum" class="span-bar">
                  <span class="mono">{{ bucket.sum }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, sumPulse.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="sumScore" class="span-score">
            <div class="card-title">这注的和值</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(sumScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(sumScore.ticket.alignment) }}</span>
                </div>
                <p class="text-xs text-muted">{{ sumScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ sumScore.ticket.sum }}</div>
                <div class="text-xs text-muted">和值</div>
              </div>
            </div>
            <div v-if="sumSpecialScored" class="span-pos">
              <div class="card-title">{{ sumPulse.special?.label || '特别号' }} <span class="sub">这注的特别号和值，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ sumScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ sumScore.special_ticket.sum }}</div>
                  <div class="text-xs text-muted">{{ spanRarityLabel(sumScore.special_ticket.rarity) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4" id="parity-pulse">
      <div class="section-head">
        <span>奇偶脉动</span>
        <span class="sub">短窗对比长窗 · 奇数升降 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ parity?.disclaimer || '奇偶脉动看主号奇数个数的历史分布与短窗升降，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="parityLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="parityShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="parityLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="parityMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="paritySpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="parityBoardLoading" @click="loadParity">
            <AppIcon v-if="parityBoardLoading" name="sync" :size="14" class="spin" />
            {{ parityBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="parityLoading" @click="runParity">
            <AppIcon v-if="parityLoading" name="sync" :size="14" class="spin" />
            {{ parityLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="parityLoading" @click="fillLatestParity">用最新开奖</button>
        </div>
        <p class="form-hint">{{ parityHint }}</p>
        <p v-if="parityError" class="bet-error">{{ parityError }}</p>

        <div v-if="parityBoardLoading && !parity" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计奇偶…
        </div>
        <div v-else-if="parity" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ parity.sample_size }} 期 · 平均 {{ spanStat(parity.mean) }} · 中位 {{ spanStat(parity.median) }}
            · 短窗 {{ spanStat(parity.short_avg) }} · 长窗 {{ spanStat(parity.long_avg) }} · 脉动 {{ spanSigned(parity.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(parity.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ parity.short }} 期</div>
            </div>
            <div class="span-drift" :class="parity.drift || 'flat'">{{ parityDriftLabel(parity.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(parity.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ parity.long }} 期</div>
            </div>
          </div>
          <div v-if="parity.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ parity.latest_draw.issue }} 期</span>
                <span>{{ parity.latest_draw.odd_count }}奇{{ parity.latest_draw.even_count }}偶</span>
              </div>
              <NumberBalls :numbers="parity.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!parity.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有开奖后，这里会看主号奇数个数的分布，以及短窗相对长窗是走高还是走低。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              奇数个数
              <span class="sub">{{ parity.basis === 'digits' ? '整注各位数字里数奇数' : '主号去重后数奇数' }}，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in parityBars" :key="bucket.odd_count" class="span-bar" :class="{ 'is-current': parityCurrent(bucket.odd_count) }">
                <span class="mono">{{ bucket.odd_count }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, parity.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <p v-if="parityBarsCollapsed" class="text-xs text-muted">奇数个数拉得比较开，这里只展开出现过的档。</p>
            <div v-if="parity.common?.length" class="span-band">
              <span class="span-tag">常见</span>
              <div class="balls">
                <span v-for="item in parity.common" :key="'c' + item.ratio" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="span-meta">{{ item.ratio }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="parity.special" class="span-pos">
              <div class="card-title">{{ parity.special.label }} <span class="sub">至少两个特别号才数奇数，不计入主号</span></div>
              <p class="text-xs text-muted">
                {{ parity.special.sample_size }} 期 · 短窗 {{ spanStat(parity.special.short_avg) }} · 长窗 {{ spanStat(parity.special.long_avg) }}
                · {{ parityDriftLabel(parity.special.drift) }}
              </p>
              <div class="span-bars">
                <div v-for="bucket in paritySpecialBars" :key="'s' + bucket.odd_count" class="span-bar">
                  <span class="mono">{{ bucket.odd_count }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, parity.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="parityScore" class="span-score">
            <div class="card-title">这注的奇偶</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(parityScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(parityScore.ticket.alignment) }}</span>
                  <span v-if="parityScore.ticket.even_count != null">{{ parityScore.ticket.odd_count }}奇{{ parityScore.ticket.even_count }}偶</span>
                  <span v-if="parityScore.ticket.imbalance != null">奇偶差 {{ parityScore.ticket.imbalance }}</span>
                </div>
                <p class="text-xs text-muted">{{ parityScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ parityScore.ticket.odd_count }}</div>
                <div class="text-xs text-muted">奇数</div>
              </div>
            </div>
            <div v-if="paritySpecialScored" class="span-pos">
              <div class="card-title">{{ parity.special?.label || '特别号' }} <span class="sub">这注的特别号奇数个数，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ parityScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ parityScore.special_ticket.odd_count }}</div>
                  <div class="text-xs text-muted">{{ spanRarityLabel(parityScore.special_ticket.rarity) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4" id="prime-pulse">
      <div class="section-head">
        <span>质合脉动</span>
        <span class="sub">短窗对比长窗 · 质数升降 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ prime?.disclaimer || '质合脉动看主号质数个数的历史分布与短窗升降，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="primeLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="primeShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="primeLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="primeMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="primeSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="primeBoardLoading" @click="loadPrime">
            <AppIcon v-if="primeBoardLoading" name="sync" :size="14" class="spin" />
            {{ primeBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="primeLoading" @click="runPrime">
            <AppIcon v-if="primeLoading" name="sync" :size="14" class="spin" />
            {{ primeLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="primeLoading" @click="fillLatestPrime">用最新开奖</button>
        </div>
        <p class="form-hint">{{ primeHint }}</p>
        <p v-if="primeError" class="bet-error">{{ primeError }}</p>

        <div v-if="primeBoardLoading && !prime" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计质合…
        </div>
        <div v-else-if="prime" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ prime.sample_size }} 期 · 平均 {{ spanStat(prime.mean) }} · 中位 {{ spanStat(prime.median) }}
            · 短窗 {{ spanStat(prime.short_avg) }} · 长窗 {{ spanStat(prime.long_avg) }} · 脉动 {{ spanSigned(prime.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(prime.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ prime.short }} 期</div>
            </div>
            <div class="span-drift" :class="prime.drift || 'flat'">{{ parityDriftLabel(prime.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(prime.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ prime.long }} 期</div>
            </div>
          </div>
          <div v-if="prime.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ prime.latest_draw.issue }} 期</span>
                <span>{{ prime.latest_draw.prime_count }}质{{ prime.latest_draw.composite_count }}合</span>
              </div>
              <NumberBalls :numbers="prime.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!prime.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有开奖后，这里会看主号质数个数的分布，以及短窗相对长窗是走高还是走低。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              质数个数
              <span class="sub">{{ prime.basis === 'digits' ? '整注各位数字里数质数' : '主号去重后数质数' }}，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in primeBars" :key="bucket.prime_count" class="span-bar" :class="{ 'is-current': primeCurrent(bucket.prime_count) }">
                <span class="mono">{{ bucket.prime_count }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, prime.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <p v-if="primeBarsCollapsed" class="text-xs text-muted">质数个数拉得比较开，这里只展开出现过的档。</p>
            <div v-if="prime.common?.length" class="span-band">
              <span class="span-tag">常见</span>
              <div class="balls">
                <span v-for="item in prime.common" :key="'c' + item.ratio" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="span-meta">{{ item.ratio }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="prime.special" class="span-pos">
              <div class="card-title">{{ prime.special.label }} <span class="sub">至少两个特别号才数质数，不计入主号</span></div>
              <p class="text-xs text-muted">
                {{ prime.special.sample_size }} 期 · 短窗 {{ spanStat(prime.special.short_avg) }} · 长窗 {{ spanStat(prime.special.long_avg) }}
                · {{ parityDriftLabel(prime.special.drift) }}
              </p>
              <div class="span-bars">
                <div v-for="bucket in primeSpecialBars" :key="'s' + bucket.prime_count" class="span-bar">
                  <span class="mono">{{ bucket.prime_count }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, prime.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="primeScore" class="span-score">
            <div class="card-title">这注的质合</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(primeScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(primeScore.ticket.alignment) }}</span>
                  <span v-if="primeScore.ticket.composite_count != null">{{ primeScore.ticket.prime_count }}质{{ primeScore.ticket.composite_count }}合</span>
                  <span v-if="primeScore.ticket.imbalance != null">质合差 {{ primeScore.ticket.imbalance }}</span>
                </div>
                <p class="text-xs text-muted">{{ primeScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ primeScore.ticket.prime_count }}</div>
                <div class="text-xs text-muted">质数</div>
              </div>
            </div>
            <div v-if="primeSpecialScored" class="span-pos">
              <div class="card-title">{{ prime.special?.label || '特别号' }} <span class="sub">这注的特别号质数个数，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ primeScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ primeScore.special_ticket.prime_count }}</div>
                  <div class="text-xs text-muted">{{ spanRarityLabel(primeScore.special_ticket.rarity) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4" id="zone-pulse">
      <div class="section-head">
        <span>区位脉动</span>
        <span class="sub">短窗对比长窗 · 三区比更偏与更匀 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ zone?.disclaimer || '区位脉动看主号三区个数配比和区位偏度，以及短窗相对长窗是更偏还是更匀，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="zoneLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="zoneShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="zoneLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="zoneMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="zoneSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="zoneBoardLoading" @click="loadZone">
            <AppIcon v-if="zoneBoardLoading" name="sync" :size="14" class="spin" />
            {{ zoneBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="zoneLoading" @click="runZone">
            <AppIcon v-if="zoneLoading" name="sync" :size="14" class="spin" />
            {{ zoneLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="zoneLoading" @click="fillLatestZone">用最新开奖</button>
        </div>
        <p class="form-hint">{{ zoneHint }}</p>
        <p v-if="zoneError" class="bet-error">{{ zoneError }}</p>

        <div v-if="zoneBoardLoading && !zone" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计区位…
        </div>
        <div v-else-if="zone" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ zone.sample_size }} 期 · 平均 {{ spanStat(zone.mean) }} · 中位 {{ spanStat(zone.median) }}
            · 短窗 {{ spanStat(zone.short_avg) }} · 长窗 {{ spanStat(zone.long_avg) }} · 脉动 {{ spanSigned(zone.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(zone.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ zone.short }} 期</div>
            </div>
            <div class="span-drift" :class="zone.drift || 'flat'">{{ zoneDriftLabel(zone.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(zone.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ zone.long }} 期</div>
            </div>
          </div>
          <div v-if="zone.avg_zone_counts" class="road-mix">
            <div v-for="item in zone.zones" :key="item.key" class="road-mix-item">
              <span class="road-mix-label">{{ zoneRangeText(item, zone.zones) }}</span>
              <span class="road-mix-num">{{ spanStat(zone.avg_zone_counts[item.key]) }}</span>
            </div>
          </div>
          <div v-if="zone.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ zone.latest_draw.issue }} 期</span>
                <span>三区比 {{ zone.latest_draw.ratio }} · 偏度 {{ zone.latest_draw.imbalance }}</span>
              </div>
              <NumberBalls :numbers="zone.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!zone.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有开奖后，这里会看三区各有几个，以及短窗相对长窗是更偏还是更匀。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              区位偏度
              <span class="sub">{{ zone.basis === 'digits' ? '整注各位按 0–3、4–6、7–9，0 和 9 不绕圈' : '主号去重后按数值区间分成三区' }}，偏度是最多一区减去最少一区，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in zoneBars" :key="bucket.imbalance" class="span-bar" :class="{ 'is-current': zoneCurrent(bucket.imbalance) }">
                <span class="mono">{{ bucket.imbalance }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, zone.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <p v-if="zoneBarsCollapsed" class="text-xs text-muted">区位偏度拉得比较开，这里只展开出现过的档。</p>
            <div v-if="zone.common?.length" class="span-band">
              <span class="span-tag">常见</span>
              <div class="balls">
                <span v-for="item in zone.common" :key="'c' + item.ratio" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="span-meta">{{ item.ratio }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="zone.special" class="span-pos">
              <div class="card-title">{{ zone.special.label }} <span class="sub">有特别号就另分三区，不计入主号</span></div>
              <p class="text-xs text-muted">
                {{ zone.special.sample_size }} 期 · 短窗 {{ spanStat(zone.special.short_avg) }} · 长窗 {{ spanStat(zone.special.long_avg) }}
                · {{ zoneDriftLabel(zone.special.drift) }}
              </p>
              <div v-if="zone.special.avg_zone_counts" class="road-mix">
                <div v-for="item in zone.special.zones" :key="'s' + item.key" class="road-mix-item">
                  <span class="road-mix-label">{{ zoneRangeText(item, zone.special.zones) }}</span>
                  <span class="road-mix-num">{{ spanStat(zone.special.avg_zone_counts[item.key]) }}</span>
                </div>
              </div>
              <div class="span-bars">
                <div v-for="bucket in zoneSpecialBars" :key="'s' + bucket.imbalance" class="span-bar">
                  <span class="mono">{{ bucket.imbalance }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, zone.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="zoneScore" class="span-score">
            <div class="card-title">这注的区位</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(zoneScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(zoneScore.ticket.alignment) }}</span>
                  <span v-if="zoneScore.ticket.ratio">三区比 {{ zoneScore.ticket.ratio }}</span>
                </div>
                <p class="text-xs text-muted">{{ zoneScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ zoneScore.ticket.imbalance }}</div>
                <div class="text-xs text-muted">区位偏度</div>
              </div>
            </div>
            <div v-if="zoneSpecialScored" class="span-pos">
              <div class="card-title">{{ zone.special?.label || '特别号' }} <span class="sub">这注的特别号区位，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ zoneScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ zoneScore.special_ticket.imbalance }}</div>
                  <div class="text-xs text-muted">{{ spanRarityLabel(zoneScore.special_ticket.rarity) }} · {{ zoneScore.special_ticket.ratio }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4" id="tail-pulse">
      <div class="section-head">
        <span>尾数脉动</span>
        <span class="sub">短窗对比长窗 · 尾数种类更散与更集中 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ tail?.disclaimer || '尾数脉动看主号不重复尾数的种类数，以及短窗相对长窗是更散还是更集中，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="tailLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="tailShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="tailLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="tailMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="tailSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="tailBoardLoading" @click="loadTail">
            <AppIcon v-if="tailBoardLoading" name="sync" :size="14" class="spin" />
            {{ tailBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="tailLoading" @click="runTail">
            <AppIcon v-if="tailLoading" name="sync" :size="14" class="spin" />
            {{ tailLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="tailLoading" @click="fillLatestTail">用最新开奖</button>
        </div>
        <p class="form-hint">{{ tailHint }}</p>
        <p v-if="tailError" class="bet-error">{{ tailError }}</p>

        <div v-if="tailBoardLoading && !tail" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计尾数…
        </div>
        <div v-else-if="tail" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ tail.sample_size }} 期 · 平均 {{ spanStat(tail.mean) }} · 中位 {{ spanStat(tail.median) }}
            · 短窗 {{ spanStat(tail.short_avg) }} · 长窗 {{ spanStat(tail.long_avg) }} · 脉动 {{ spanSigned(tail.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(tail.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ tail.short }} 期</div>
            </div>
            <div class="span-drift" :class="tail.drift || 'flat'">{{ tailDriftLabel(tail.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(tail.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ tail.long }} 期</div>
            </div>
          </div>
          <div v-if="tail.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ tail.latest_draw.issue }} 期</span>
                <span>尾数 {{ tailSpeak(tail.latest_draw.tails) }} · 种类 {{ tail.latest_draw.unique_tail_count }}</span>
              </div>
              <NumberBalls :numbers="tail.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!tail.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有开奖后，这里会看主号有几种尾数，以及短窗相对长窗是更散还是更集中。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              尾数种类
              <span class="sub">{{ tail.basis === 'digits' ? '整注各位本身就是尾数，0 和 9 不绕圈' : '主号去重后取个位，同一尾数只算一种' }}，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in tailBars" :key="bucket.unique_tail_count" class="span-bar" :class="{ 'is-current': tailCurrent(bucket.unique_tail_count) }">
                <span class="mono">{{ bucket.unique_tail_count }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, tail.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <p v-if="tailBarsCollapsed" class="text-xs text-muted">尾数种类拉得比较开，这里只展开出现过的档。</p>
            <div v-if="tail.common?.length" class="span-band">
              <span class="span-tag">常见组合</span>
              <div class="balls">
                <span v-for="item in tail.common" :key="'t' + item.pattern" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="span-meta">{{ tailSpeak(item.tails) }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="tail.special" class="span-pos">
              <div class="card-title">{{ tail.special.label }} <span class="sub">有特别号就另计尾数，不计入主号</span></div>
              <p class="text-xs text-muted">
                {{ tail.special.sample_size }} 期 · 短窗 {{ spanStat(tail.special.short_avg) }} · 长窗 {{ spanStat(tail.special.long_avg) }}
                · {{ tailDriftLabel(tail.special.drift) }}
              </p>
              <div class="span-bars">
                <div v-for="bucket in tailSpecialBars" :key="'ts' + bucket.unique_tail_count" class="span-bar">
                  <span class="mono">{{ bucket.unique_tail_count }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, tail.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="tailScore" class="span-score">
            <div class="card-title">这注的尾数</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(tailScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(tailScore.ticket.alignment) }}</span>
                  <span v-if="tailScore.ticket.tails">尾数 {{ tailSpeak(tailScore.ticket.tails) }}</span>
                </div>
                <p class="text-xs text-muted">{{ tailScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ tailScore.ticket.unique_tail_count }}</div>
                <div class="text-xs text-muted">尾数种类</div>
              </div>
            </div>
            <div v-if="tailSpecialScored" class="span-pos">
              <div class="card-title">{{ tail.special?.label || '特别号' }} <span class="sub">这注的特别号尾数，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ tailScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ tailScore.special_ticket.unique_tail_count }}</div>
                  <div class="text-xs text-muted">{{ spanRarityLabel(tailScore.special_ticket.rarity) }} · {{ tailSpeak(tailScore.special_ticket.tails) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4" id="ac-pulse">
      <div class="section-head">
        <span>AC值脉动</span>
        <span class="sub">短窗对比长窗 · 算术复杂度升降 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ acPulse?.disclaimer || 'AC值脉动看主号算术复杂度的历史分布，以及短窗相对长窗是走高还是走低，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="acLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="acShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="acLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="acMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="acSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="acBoardLoading" @click="loadAc">
            <AppIcon v-if="acBoardLoading" name="sync" :size="14" class="spin" />
            {{ acBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="acLoading" @click="runAc">
            <AppIcon v-if="acLoading" name="sync" :size="14" class="spin" />
            {{ acLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="acLoading" @click="fillLatestAc">用最新开奖</button>
        </div>
        <p class="form-hint">{{ acHint }}</p>
        <p v-if="acError" class="bet-error">{{ acError }}</p>

        <div v-if="acBoardLoading && !acPulse" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计 AC 值…
        </div>
        <div v-else-if="acPulse" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ acPulse.sample_size }} 期 · 平均 {{ spanStat(acPulse.mean) }} · 中位 {{ spanStat(acPulse.median) }}
            · 短窗 {{ spanStat(acPulse.short_avg) }} · 长窗 {{ spanStat(acPulse.long_avg) }} · 脉动 {{ spanSigned(acPulse.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(acPulse.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ acPulse.short }} 期</div>
            </div>
            <div class="span-drift" :class="acPulse.drift || 'flat'">{{ acDriftLabel(acPulse.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(acPulse.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ acPulse.long }} 期</div>
            </div>
          </div>
          <div v-if="acPulse.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ acPulse.latest_draw.issue }} 期</span>
                <span>AC值 {{ spanStat(acPulse.latest_draw.ac_value) }}</span>
              </div>
              <NumberBalls :numbers="acPulse.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!acPulse.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有开奖后，这里会看主号算术复杂度的分布，以及短窗相对长窗是走高还是走低。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              AC值分布
              <span class="sub">{{ acPulse.basis === 'digits' ? '整注各位数字从小到大排列，0 和 9 不绕圈' : '主号去重后从小到大排列，两两差值去重再减去个数减一' }}，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in acBars" :key="bucket.ac_value" class="span-bar" :class="{ 'is-current': acCurrent(bucket.ac_value) }">
                <span class="mono">{{ bucket.ac_value }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, acPulse.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <p v-if="acBarsCollapsed" class="text-xs text-muted">AC值拉得比较开，这里只展开出现过的档。</p>
            <div v-if="acPulse.common?.length" class="span-band">
              <span class="span-tag">常见</span>
              <div class="balls">
                <span v-for="item in acPulse.common" :key="'ac' + item.ac_value" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="ball sm" :class="ballClass(type)">{{ item.ac_value }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="acPulse.special" class="span-pos">
              <div class="card-title">{{ acPulse.special.label }} <span class="sub">至少两个特别号才算算术复杂度，不计入主号</span></div>
              <p class="text-xs text-muted">
                {{ acPulse.special.sample_size }} 期 · 短窗 {{ spanStat(acPulse.special.short_avg) }} · 长窗 {{ spanStat(acPulse.special.long_avg) }}
                · {{ acDriftLabel(acPulse.special.drift) }}
              </p>
              <div class="span-bars">
                <div v-for="bucket in acSpecialBars" :key="'acs' + bucket.ac_value" class="span-bar">
                  <span class="mono">{{ bucket.ac_value }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, acPulse.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="acScore" class="span-score">
            <div class="card-title">这注的 AC 值</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(acScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(acScore.ticket.alignment) }}</span>
                </div>
                <p class="text-xs text-muted">{{ acScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ spanStat(acScore.ticket.ac_value) }}</div>
                <div class="text-xs text-muted">AC值</div>
              </div>
            </div>
            <div v-if="acSpecialScored" class="span-pos">
              <div class="card-title">{{ acPulse.special?.label || '特别号' }} <span class="sub">这注的特别号算术复杂度，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ acScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ spanStat(acScore.special_ticket.ac_value) }}</div>
                  <div class="text-xs text-muted">{{ spanRarityLabel(acScore.special_ticket.rarity) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4" id="hewei-pulse">
      <div class="section-head">
        <span>和尾脉动</span>
        <span class="sub">短窗对比长窗 · 和值个位升降 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ heweiPulse?.disclaimer || '和尾脉动看主号和值个位的历史分布，以及短窗相对长窗是走高还是走低，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="heweiLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="heweiShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="heweiLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="heweiMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="heweiSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="heweiBoardLoading" @click="loadHewei">
            <AppIcon v-if="heweiBoardLoading" name="sync" :size="14" class="spin" />
            {{ heweiBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="heweiLoading" @click="runHewei">
            <AppIcon v-if="heweiLoading" name="sync" :size="14" class="spin" />
            {{ heweiLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="heweiLoading" @click="fillLatestHewei">用最新开奖</button>
        </div>
        <p class="form-hint">{{ heweiHint }}</p>
        <p v-if="heweiError" class="bet-error">{{ heweiError }}</p>

        <div v-if="heweiBoardLoading && !heweiPulse" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计和尾…
        </div>
        <div v-else-if="heweiPulse" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ heweiPulse.sample_size }} 期 · 平均 {{ spanStat(heweiPulse.mean) }} · 中位 {{ spanStat(heweiPulse.median) }}
            · 短窗 {{ spanStat(heweiPulse.short_avg) }} · 长窗 {{ spanStat(heweiPulse.long_avg) }} · 脉动 {{ spanSigned(heweiPulse.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(heweiPulse.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ heweiPulse.short }} 期</div>
            </div>
            <div class="span-drift" :class="heweiPulse.drift || 'flat'">{{ heweiDriftLabel(heweiPulse.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(heweiPulse.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ heweiPulse.long }} 期</div>
            </div>
          </div>
          <div v-if="heweiPulse.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ heweiPulse.latest_draw.issue }} 期</span>
                <span>和尾 {{ spanStat(heweiPulse.latest_draw.hewei) }}</span>
              </div>
              <NumberBalls :numbers="heweiPulse.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!heweiPulse.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有开奖后，这里会看主号和值个位的分布，以及短窗相对长窗是走高还是走低。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              和尾分布
              <span class="sub">{{ heweiPulse.basis === 'digits' ? '整注各位相加取个位，重复保留，0 和 9 不绕圈' : '主号去重后相加取个位' }}，0–9 十档，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in heweiBars" :key="bucket.hewei" class="span-bar" :class="{ 'is-current': heweiCurrent(bucket.hewei) }">
                <span class="mono">{{ bucket.hewei }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, heweiPulse.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <div v-if="heweiPulse.common?.length" class="span-band">
              <span class="span-tag">常见</span>
              <div class="balls">
                <span v-for="item in heweiPulse.common" :key="'hw' + item.hewei" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="ball sm" :class="ballClass(type)">{{ item.hewei }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="heweiPulse.special" class="span-pos">
              <div class="card-title">{{ heweiPulse.special.label }} <span class="sub">有特别号就另算和尾，不计入主号</span></div>
              <p class="text-xs text-muted">
                {{ heweiPulse.special.sample_size }} 期 · 短窗 {{ spanStat(heweiPulse.special.short_avg) }} · 长窗 {{ spanStat(heweiPulse.special.long_avg) }}
                · {{ heweiDriftLabel(heweiPulse.special.drift) }}
              </p>
              <div class="span-bars">
                <div v-for="bucket in heweiSpecialBars" :key="'hws' + bucket.hewei" class="span-bar">
                  <span class="mono">{{ bucket.hewei }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, heweiPulse.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="heweiScore" class="span-score">
            <div class="card-title">这注的和尾</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(heweiScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(heweiScore.ticket.alignment) }}</span>
                </div>
                <p class="text-xs text-muted">{{ heweiScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ spanStat(heweiScore.ticket.hewei) }}</div>
                <div class="text-xs text-muted">和尾</div>
              </div>
            </div>
            <div v-if="heweiSpecialScored" class="span-pos">
              <div class="card-title">{{ heweiPulse.special?.label || '特别号' }} <span class="sub">这注的特别号和尾，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ heweiScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ spanStat(heweiScore.special_ticket.hewei) }}</div>
                  <div class="text-xs text-muted">{{ spanRarityLabel(heweiScore.special_ticket.rarity) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4" id="daxiao-pulse">
      <div class="section-head">
        <span>大小脉动</span>
        <span class="sub">短窗对比长窗 · 大号个数升降 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ daxiao?.disclaimer || '大小脉动看主号大号个数的历史分布，以及短窗相对长窗是走高还是走低，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="daxiaoLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="daxiaoShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="daxiaoLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="daxiaoMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="daxiaoSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="daxiaoBoardLoading" @click="loadDaxiao">
            <AppIcon v-if="daxiaoBoardLoading" name="sync" :size="14" class="spin" />
            {{ daxiaoBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="daxiaoLoading" @click="runDaxiao">
            <AppIcon v-if="daxiaoLoading" name="sync" :size="14" class="spin" />
            {{ daxiaoLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="daxiaoLoading" @click="fillLatestDaxiao">用最新开奖</button>
        </div>
        <p class="form-hint">{{ daxiaoHint }}</p>
        <p v-if="daxiaoError" class="bet-error">{{ daxiaoError }}</p>

        <div v-if="daxiaoBoardLoading && !daxiao" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计大小…
        </div>
        <div v-else-if="daxiao" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ daxiao.sample_size }} 期 · 平均 {{ spanStat(daxiao.mean) }} · 中位 {{ spanStat(daxiao.median) }}
            · 短窗 {{ spanStat(daxiao.short_avg) }} · 长窗 {{ spanStat(daxiao.long_avg) }} · 脉动 {{ spanSigned(daxiao.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(daxiao.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ daxiao.short }} 期</div>
            </div>
            <div class="span-drift" :class="daxiao.drift || 'flat'">{{ daxiaoDriftLabel(daxiao.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(daxiao.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ daxiao.long }} 期</div>
            </div>
          </div>
          <div v-if="daxiao.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ daxiao.latest_draw.issue }} 期</span>
                <span>{{ daxiaoRatio(daxiao.latest_draw.big_count, daxiao.latest_draw.small_count) }}</span>
              </div>
              <NumberBalls :numbers="daxiao.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!daxiao.sample_size" class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有开奖后，这里会看主号大号个数的分布，以及短窗相对长窗是走高还是走低。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              大号个数
              <span class="sub">{{ daxiaoCutoff(daxiao.boundary) }}，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in daxiaoBars" :key="bucket.big_count" class="span-bar" :class="{ 'is-current': daxiaoCurrent(bucket.big_count) }">
                <span class="mono">{{ bucket.big_count }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, daxiao.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <div v-if="daxiao.common?.length" class="span-band">
              <span class="span-tag">常见</span>
              <div class="balls">
                <span v-for="item in daxiao.common" :key="'dx' + item.ratio" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="span-meta">{{ item.ratio }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="daxiao.special" class="span-pos">
              <div class="card-title">{{ daxiao.special.label }} <span class="sub">有特别号就另算大号个数，不计入主号 · {{ daxiaoCutoff(daxiao.special.boundary) }}</span></div>
              <p class="text-xs text-muted">
                {{ daxiao.special.sample_size }} 期 · 短窗 {{ spanStat(daxiao.special.short_avg) }} · 长窗 {{ spanStat(daxiao.special.long_avg) }}
                · {{ daxiaoDriftLabel(daxiao.special.drift) }}
              </p>
              <div class="span-bars">
                <div v-for="bucket in daxiaoSpecialBars" :key="'dxs' + bucket.big_count" class="span-bar">
                  <span class="mono">{{ bucket.big_count }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, daxiao.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="daxiaoScore" class="span-score">
            <div class="card-title">这注的大小</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(daxiaoScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(daxiaoScore.ticket.alignment) }}</span>
                  <span v-if="daxiaoScore.ticket.small_count != null">{{ daxiaoRatio(daxiaoScore.ticket.big_count, daxiaoScore.ticket.small_count) }}</span>
                </div>
                <p class="text-xs text-muted">{{ daxiaoScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ spanStat(daxiaoScore.ticket.big_count) }}</div>
                <div class="text-xs text-muted">大号</div>
              </div>
            </div>
            <div v-if="daxiaoSpecialScored" class="span-pos">
              <div class="card-title">{{ daxiao.special?.label || '特别号' }} <span class="sub">这注的特别号大号个数，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ daxiaoScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ spanStat(daxiaoScore.special_ticket.big_count) }}</div>
                  <div class="text-xs text-muted">{{ spanRarityLabel(daxiaoScore.special_ticket.rarity) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4" id="shengping-pulse">
      <div class="section-head">
        <span>升平降脉动</span>
        <span class="sub">短窗对比长窗 · 同位升降个数 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ shengping?.disclaimer || '升平降脉动看主号升的个数的历史分布，以及短窗相对长窗是走高还是走低，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="shengpingLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="shengpingShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="shengpingLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="shengpingMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="shengpingSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="shengpingBoardLoading" @click="loadShengping">
            <AppIcon v-if="shengpingBoardLoading" name="sync" :size="14" class="spin" />
            {{ shengpingBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="shengpingLoading" @click="runShengping">
            <AppIcon v-if="shengpingLoading" name="sync" :size="14" class="spin" />
            {{ shengpingLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="shengpingLoading" @click="fillLatestShengping">用最新开奖</button>
        </div>
        <p class="form-hint">{{ shengpingHint }}</p>
        <p v-if="shengpingError" class="bet-error">{{ shengpingError }}</p>

        <div v-if="shengpingBoardLoading && !shengping" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计升平降…
        </div>
        <div v-else-if="shengping" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ shengping.sample_size }} 期 · 平均 {{ spanStat(shengping.mean) }} · 中位 {{ spanStat(shengping.median) }}
            · 短窗 {{ spanStat(shengping.short_avg) }} · 长窗 {{ spanStat(shengping.long_avg) }} · 脉动 {{ spanSigned(shengping.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(shengping.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ shengping.short }} 期</div>
            </div>
            <div class="span-drift" :class="shengping.drift || 'flat'">{{ shengpingDriftLabel(shengping.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(shengping.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ shengping.long }} 期</div>
            </div>
          </div>
          <div v-if="shengping.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ shengping.latest_draw.issue }} 期</span>
                <span>{{ shengping.latest_draw.pattern || '暂无上期' }}</span>
              </div>
              <NumberBalls :numbers="shengping.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!shengping.sample_size" class="empty">
            <div class="empty-title">暂无对照</div>
            <div class="empty-desc">有相邻两期开奖后，这里会看主号升的个数，以及短窗相对长窗是走高还是走低。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              升的个数
              <span class="sub">{{ shengping.basis === 'digits' ? '按位比较，保留重复，不排序' : '去重升序后按标准个数对齐' }}，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in shengpingBars" :key="bucket.rise_count" class="span-bar" :class="{ 'is-current': shengpingCurrent(bucket.rise_count) }">
                <span class="mono">{{ bucket.rise_count }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, shengping.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <div v-if="shengping.common?.length" class="span-band">
              <span class="span-tag">常见</span>
              <div class="balls">
                <span v-for="item in shengping.common" :key="'sp' + item.pattern" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="span-meta">{{ item.pattern }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="shengping.special" class="span-pos">
              <div class="card-title">{{ shengping.special.label }} <span class="sub">有特别号就另算升平降，不计入主号</span></div>
              <p class="text-xs text-muted">
                {{ shengping.special.sample_size }} 期 · 短窗 {{ spanStat(shengping.special.short_avg) }} · 长窗 {{ spanStat(shengping.special.long_avg) }}
                · {{ shengpingDriftLabel(shengping.special.drift) }}
              </p>
              <div class="span-bars">
                <div v-for="bucket in shengpingSpecialBars" :key="'sps' + bucket.rise_count" class="span-bar">
                  <span class="mono">{{ bucket.rise_count }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, shengping.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="shengpingScore" class="span-score">
            <div class="card-title">这注的升平降</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(shengpingScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(shengpingScore.ticket.alignment) }}</span>
                  <span v-if="shengpingScore.ticket.pattern">{{ shengpingScore.ticket.pattern }}</span>
                </div>
                <p class="text-xs text-muted">{{ shengpingScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ spanStat(shengpingScore.ticket.rise_count) }}</div>
                <div class="text-xs text-muted">升</div>
              </div>
            </div>
            <div v-if="shengpingSpecialScored" class="span-pos">
              <div class="card-title">{{ shengping.special?.label || '特别号' }} <span class="sub">这注的特别号升平降，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ shengpingScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ spanStat(shengpingScore.special_ticket.rise_count) }}</div>
                  <div class="text-xs text-muted">{{ shengpingScore.special_ticket.pattern || spanRarityLabel(shengpingScore.special_ticket.rarity) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4" id="zhenfu-pulse">
      <div class="section-head">
        <span>振幅脉动</span>
        <span class="sub">短窗对比长窗 · 同位绝对差之和 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ zhenfu?.disclaimer || '振幅脉动看主号相邻两期绝对差之和的历史分布，以及短窗相对长窗是走高还是走低，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="zhenfuLimit" class="form-input mono" type="number" min="5" max="200" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="zhenfuShort" class="form-input mono" type="number" min="5" max="30" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="zhenfuLong" class="form-input mono" type="number" min="20" max="200" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="zhenfuMain" class="form-input mono" :placeholder="echoField.main" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="zhenfuSpecial" class="form-input mono" :placeholder="echoField.special" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="zhenfuBoardLoading" @click="loadZhenfu">
            <AppIcon v-if="zhenfuBoardLoading" name="sync" :size="14" class="spin" />
            {{ zhenfuBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="zhenfuLoading" @click="runZhenfu">
            <AppIcon v-if="zhenfuLoading" name="sync" :size="14" class="spin" />
            {{ zhenfuLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="zhenfuLoading" @click="fillLatestZhenfu">用最新开奖</button>
        </div>
        <p class="form-hint">{{ zhenfuHint }}</p>
        <p v-if="zhenfuError" class="bet-error">{{ zhenfuError }}</p>

        <div v-if="zhenfuBoardLoading && !zhenfu" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计振幅…
        </div>
        <div v-else-if="zhenfu" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ zhenfu.sample_size }} 期 · 平均 {{ spanStat(zhenfu.mean) }} · 中位 {{ spanStat(zhenfu.median) }}
            · 短窗 {{ spanStat(zhenfu.short_avg) }} · 长窗 {{ spanStat(zhenfu.long_avg) }} · 脉动 {{ spanSigned(zhenfu.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(zhenfu.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ zhenfu.short }} 期</div>
            </div>
            <div class="span-drift" :class="zhenfu.drift || 'flat'">{{ zhenfuDriftLabel(zhenfu.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(zhenfu.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ zhenfu.long }} 期</div>
            </div>
          </div>
          <div v-if="zhenfu.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ zhenfu.latest_draw.issue }} 期</span>
                <span>{{ zhenfu.latest_draw.amplitude_sum == null ? '暂无上期' : `振幅 ${zhenfu.latest_draw.amplitude_sum}` }}</span>
              </div>
              <NumberBalls :numbers="zhenfu.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!zhenfu.sample_size" class="empty">
            <div class="empty-title">暂无对照</div>
            <div class="empty-desc">有相邻两期开奖后，这里会看主号振幅，以及短窗相对长窗是走高还是走低。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              振幅
              <span class="sub">{{ zhenfu.basis === 'digits' ? '按位比较，保留重复，不排序' : '去重升序后按标准个数对齐' }}，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in zhenfuBars" :key="bucket.amplitude_sum" class="span-bar" :class="{ 'is-current': zhenfuCurrent(bucket.amplitude_sum) }">
                <span class="mono">{{ bucket.amplitude_sum }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, zhenfu.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <div v-if="zhenfu.common?.length" class="span-band">
              <span class="span-tag">常见</span>
              <div class="balls">
                <span v-for="item in zhenfu.common" :key="'zf' + item.amplitude_sum" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="span-meta">{{ item.amplitude_sum }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="zhenfu.special" class="span-pos">
              <div class="card-title">{{ zhenfu.special.label }} <span class="sub">有特别号就另算振幅，不计入主号</span></div>
              <p class="text-xs text-muted">
                {{ zhenfu.special.sample_size }} 期 · 短窗 {{ spanStat(zhenfu.special.short_avg) }} · 长窗 {{ spanStat(zhenfu.special.long_avg) }}
                · {{ zhenfuDriftLabel(zhenfu.special.drift) }}
              </p>
              <div class="span-bars">
                <div v-for="bucket in zhenfuSpecialBars" :key="'zfs' + bucket.amplitude_sum" class="span-bar">
                  <span class="mono">{{ bucket.amplitude_sum }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, zhenfu.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="zhenfuScore" class="span-score">
            <div class="card-title">这注的振幅</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(zhenfuScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(zhenfuScore.ticket.alignment) }}</span>
                </div>
                <p class="text-xs text-muted">{{ zhenfuScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ spanStat(zhenfuScore.ticket.amplitude_sum) }}</div>
                <div class="text-xs text-muted">振幅</div>
              </div>
            </div>
            <div v-if="zhenfuSpecialScored" class="span-pos">
              <div class="card-title">{{ zhenfu.special?.label || '特别号' }} <span class="sub">这注的特别号振幅，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ zhenfuScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ spanStat(zhenfuScore.special_ticket.amplitude_sum) }}</div>
                  <div class="text-xs text-muted">{{ spanRarityLabel(zhenfuScore.special_ticket.rarity) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4" id="junzhi-pulse">
      <div class="section-head">
        <span>均值脉动</span>
        <span class="sub">短窗对比长窗 · 主号算术平均 · 仅供娱乐，不构成投注建议</span>
      </div>
      <div class="card">
        <div class="alert alert-disclaimer">
          <AppIcon name="info" :size="14" style="margin-top:1px;flex:none" />
          <div>{{ junzhi?.disclaimer || '均值脉动看主号算术平均的历史分布，以及短窗相对长窗是走高还是走低，仅供娱乐，不构成投注建议。' }}</div>
        </div>
        <div class="form-row span-windows">
          <div class="form-group">
            <label class="form-label">样本（期）</label>
            <input v-model.number="junzhiLimit" class="form-input mono" type="number" min="5" max="200" @keydown.enter="loadJunzhi" />
          </div>
          <div class="form-group">
            <label class="form-label">短窗（期）</label>
            <input v-model.number="junzhiShort" class="form-input mono" type="number" min="5" max="30" @keydown.enter="loadJunzhi" />
          </div>
          <div class="form-group">
            <label class="form-label">长窗（期）</label>
            <input v-model.number="junzhiLong" class="form-input mono" type="number" min="20" max="200" @keydown.enter="loadJunzhi" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">主号</label>
            <input v-model="junzhiMain" class="form-input mono" :placeholder="echoField.main" @keydown.enter="runJunzhi" />
          </div>
          <div v-if="echoField.specialLabel" class="form-group">
            <label class="form-label">{{ echoField.specialLabel }}</label>
            <input v-model="junzhiSpecial" class="form-input mono" :placeholder="echoField.special" @keydown.enter="runJunzhi" />
          </div>
        </div>
        <div class="predict-actions">
          <button class="btn btn-ghost" type="button" :disabled="junzhiBoardLoading" @click="loadJunzhi">
            <AppIcon v-if="junzhiBoardLoading" name="sync" :size="14" class="spin" />
            {{ junzhiBoardLoading ? '统计中…' : '刷新脉动' }}
          </button>
          <button class="btn btn-primary" type="button" :disabled="junzhiLoading" @click="runJunzhi">
            <AppIcon v-if="junzhiLoading" name="sync" :size="14" class="spin" />
            {{ junzhiLoading ? '打分中…' : '给这注打分' }}
          </button>
          <button class="btn btn-ghost" type="button" :disabled="junzhiLoading" @click="fillLatestJunzhi">用最新开奖</button>
        </div>
        <p class="form-hint">{{ junzhiHint }}</p>
        <p v-if="junzhiError" class="bet-error">{{ junzhiError }}</p>

        <div v-if="junzhiBoardLoading && !junzhi" class="loading-line">
          <AppIcon name="sync" :size="15" class="spin" />统计均值…
        </div>
        <div v-else-if="junzhi" class="span-list">
          <p class="text-xs text-muted">
            样本 {{ junzhi.sample_size }} 期 · 平均 {{ spanStat(junzhi.mean) }} · 中位 {{ spanStat(junzhi.median) }}
            · 短窗 {{ spanStat(junzhi.short_avg) }} · 长窗 {{ spanStat(junzhi.long_avg) }} · 脉动 {{ spanSigned(junzhi.pulse) }}
          </p>
          <div class="span-meter">
            <div>
              <div class="span-meter-num">{{ spanStat(junzhi.short_avg) }}</div>
              <div class="text-xs text-muted">短窗 {{ junzhi.short }} 期</div>
            </div>
            <div class="span-drift" :class="junzhi.drift || 'flat'">{{ junzhiDriftLabel(junzhi.drift) }}</div>
            <div>
              <div class="span-meter-num">{{ spanStat(junzhi.long_avg) }}</div>
              <div class="text-xs text-muted">长窗 {{ junzhi.long }} 期</div>
            </div>
          </div>
          <div v-if="junzhi.latest_draw" class="span-row">
            <div class="echo-draw">
              <div class="echo-meta">
                <span>最新开奖</span>
                <span class="mono">第 {{ junzhi.latest_draw.issue }} 期</span>
                <span>均值 {{ spanStat(junzhi.latest_draw.mean_value) }}</span>
              </div>
              <NumberBalls :numbers="junzhi.latest_draw" :type="type" size="sm" />
            </div>
          </div>
          <div v-if="!junzhi.sample_size" class="empty">
            <div class="empty-title">暂无对照</div>
            <div class="empty-desc">有开奖后，这里会看主号均值，以及短窗相对长窗是走高还是走低。仅供娱乐，不构成投注建议。</div>
          </div>
          <template v-else>
            <div class="card-title">
              均值
              <span class="sub">{{ junzhi.basis === 'digits' ? '按位取平均，保留重复，不排序' : '主号去重后取算术平均' }}，特别号不计入</span>
            </div>
            <div class="span-bars">
              <div v-for="bucket in junzhiBars" :key="bucket.mean_value" class="span-bar" :class="{ 'is-current': junzhiCurrent(bucket.mean_value) }">
                <span class="mono">{{ spanStat(bucket.mean_value) }}</span>
                <span class="span-bar-track">
                  <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, junzhi.distribution) }" />
                </span>
                <span class="mono">{{ bucket.count }}</span>
              </div>
            </div>
            <div v-if="junzhi.common?.length" class="span-band">
              <span class="span-tag">常见</span>
              <div class="balls">
                <span v-for="item in junzhi.common" :key="'jz' + item.mean_value" class="span-chip" :title="`出现 ${item.count} 次`">
                  <span class="span-meta">{{ spanStat(item.mean_value) }}</span>
                  <span class="span-meta">{{ item.count }}</span>
                </span>
              </div>
            </div>
            <div v-if="junzhi.special" class="span-pos">
              <div class="card-title">{{ junzhi.special.label }} <span class="sub">有特别号就另算均值，不计入主号</span></div>
              <p class="text-xs text-muted">
                {{ junzhi.special.sample_size }} 期 · 短窗 {{ spanStat(junzhi.special.short_avg) }} · 长窗 {{ spanStat(junzhi.special.long_avg) }}
                · {{ junzhiDriftLabel(junzhi.special.drift) }}
              </p>
              <div class="span-bars">
                <div v-for="bucket in junzhiSpecialBars" :key="'jzs' + bucket.mean_value" class="span-bar">
                  <span class="mono">{{ spanStat(bucket.mean_value) }}</span>
                  <span class="span-bar-track">
                    <span class="span-bar-fill" :style="{ width: spanBarWidth(bucket.count, junzhi.special.distribution) }" />
                  </span>
                  <span class="mono">{{ bucket.count }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-if="junzhiScore" class="span-score">
            <div class="card-title">这注的均值</div>
            <div class="span-row">
              <div class="echo-draw">
                <div class="echo-meta">
                  <span>{{ spanRarityLabel(junzhiScore.ticket.rarity) }}</span>
                  <span>{{ spanAlignLabel(junzhiScore.ticket.alignment) }}</span>
                </div>
                <p class="text-xs text-muted">{{ junzhiScore.ticket.note }}</p>
              </div>
              <div class="echo-score">
                <div class="echo-score-num">{{ spanStat(junzhiScore.ticket.mean_value) }}</div>
                <div class="text-xs text-muted">均值</div>
              </div>
            </div>
            <div v-if="junzhiSpecialScored" class="span-pos">
              <div class="card-title">{{ junzhi.special?.label || '特别号' }} <span class="sub">这注的特别号均值，不计入主号</span></div>
              <div class="span-row">
                <p class="text-xs text-muted">{{ junzhiScore.special_ticket.note }}</p>
                <div class="echo-score">
                  <div class="echo-score-num">{{ spanStat(junzhiScore.special_ticket.mean_value) }}</div>
                  <div class="text-xs text-muted">{{ spanRarityLabel(junzhiScore.special_ticket.rarity) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading-line"><AppIcon name="sync" :size="15" class="spin" />分析中…</div>
    <template v-else-if="data">
      <div class="grid grid-2 mb-4">
        <div class="card">
          <div class="card-title">主号频次 <span class="sub">柱越高越热</span></div>
          <div class="bar-chart">
            <div
              v-for="f in displayFreq"
              :key="f.n"
              class="bar"
              :style="{ height: barH(f.count) + '%' }"
              :title="`${f.n}: ${f.count}`"
            >
              <span class="tip" v-if="f.count">{{ f.count }}</span>
            </div>
          </div>
          <div class="bar-labels">
            <span v-for="f in displayFreq" :key="'l'+f.n">{{ f.n }}</span>
          </div>
        </div>
        <div class="card">
          <div class="card-title">热力 <span class="sub">灰度 + 蓝灰强调</span></div>
          <div class="heatmap" :style="heatGrid">
            <div
              v-for="h in data.heatmap"
              :key="h.n"
              class="heat-cell"
              :data-v="h.level"
            >{{ h.n }}</div>
          </div>
        </div>
      </div>

      <div class="grid grid-2 mb-4">
        <div class="card">
          <div class="card-title">热号 Top</div>
          <div class="balls">
            <span v-for="h in data.hot_main" :key="h.n" class="ball" :class="ballClass(type)">{{ h.n }}</span>
          </div>
          <p class="text-xs text-muted mt-3">出现次数：{{ data.hot_main.map(h => h.count).join(', ') }}</p>
        </div>
        <div class="card">
          <div class="card-title">冷号 Top</div>
          <div class="balls">
            <span v-for="h in data.cold_main" :key="h.n" class="ball ghost">{{ h.n }}</span>
          </div>
          <p class="text-xs text-muted mt-3">出现次数：{{ data.cold_main.map(h => h.count).join(', ') }}</p>
        </div>
      </div>

      <div v-if="shape" class="mb-4">
        <div class="section-head">
          <span>号码形态</span>
          <span class="sub">近 {{ shape.sample_size }} 期主号 · 不含蓝球/特别号 · 仅供娱乐</span>
        </div>
        <div v-if="!shape.sample_size" class="card">
          <div class="empty">
            <div class="empty-title">暂无开奖</div>
            <div class="empty-desc">有主号样本后，这里会统计奇偶、大小、和值与连号</div>
          </div>
        </div>
        <template v-else>
          <div class="grid grid-4 mb-4">
            <div class="card stat">
              <div class="stat-label">和值均值</div>
              <div class="stat-value">{{ shape.sum.avg }}</div>
            </div>
            <div class="card stat">
              <div class="stat-label">{{ shape.mode === 'set' ? '含连号' : '跨度均值' }}</div>
              <div class="stat-value">{{ shape.mode === 'set' ? `${shape.consecutive.draws_with}/${shape.sample_size}` : shape.span.avg }}</div>
            </div>
            <div class="card stat">
              <div class="stat-label">常见奇偶</div>
              <div class="stat-value compact">{{ shape.odd_even[0]?.label || '—' }}</div>
            </div>
            <div class="card stat">
              <div class="stat-label">常见大小</div>
              <div class="stat-value compact">{{ shape.big_small[0]?.label || '—' }}</div>
            </div>
          </div>
          <p class="text-xs text-muted mb-4">
            连号 {{ shape.consecutive.draws_with }} 期，平均 {{ shape.consecutive.avg_pairs }} 组
            · 和值 {{ shape.sum.min }}–{{ shape.sum.max }}
            · 跨度 {{ shape.span.min }}–{{ shape.span.max }}
          </p>
          <div class="grid grid-2 mb-4">
            <div class="card">
              <div class="card-title">奇偶 <span class="sub">主号个数</span></div>
              <div class="table-wrap table-wrap-plain">
                <table>
                  <thead><tr><th>比例</th><th>期数</th></tr></thead>
                  <tbody>
                    <tr v-for="row in shape.odd_even.slice(0, 8)" :key="row.label">
                      <td>{{ row.label }}</td>
                      <td class="mono">{{ row.count }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            <div class="card">
              <div class="card-title">和值区间</div>
              <div class="table-wrap table-wrap-plain">
                <table>
                  <thead><tr><th>区间</th><th>期数</th></tr></thead>
                  <tbody>
                    <tr v-for="row in shape.sum.buckets" :key="row.label">
                      <td class="mono">{{ row.label }}</td>
                      <td class="mono">{{ row.count }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          <div v-if="shape.zones.length || shape.patterns.length" class="grid grid-2">
            <div v-if="shape.zones.length" class="card">
              <div class="card-title">区间 <span class="sub">平均个数</span></div>
              <div class="table-wrap table-wrap-plain">
                <table>
                  <thead><tr><th>区间</th><th>平均</th></tr></thead>
                  <tbody>
                    <tr v-for="row in shape.zones" :key="row.label">
                      <td>{{ row.label }}</td>
                      <td class="mono">{{ row.avg }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            <div v-if="shape.patterns.length" class="card">
              <div class="card-title">三位形态</div>
              <div class="table-wrap table-wrap-plain">
                <table>
                  <thead><tr><th>形态</th><th>期数</th></tr></thead>
                  <tbody>
                    <tr v-for="row in shape.patterns" :key="row.label">
                      <td>{{ row.label }}</td>
                      <td class="mono">{{ row.count }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </template>
      </div>

      <div class="card">
        <div class="card-title">遗漏（距今期数）</div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>号码</th><th>遗漏</th><th>号码</th><th>遗漏</th><th>号码</th><th>遗漏</th></tr></thead>
            <tbody>
              <tr v-for="(row, i) in omitRows" :key="i">
                <td class="mono" v-for="(cell, j) in row" :key="j">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api, TYPE_NAMES, ballClass, getMomentum, postMomentum, getNeighbor, postNeighbor, getSpan, postSpan, getCluster, postCluster, getRoad, postRoad, getSum, postSum, getParity, postParity, getPrime, postPrime, getZone, postZone, getTail, postTail, getAc, postAc, getHewei, postHewei, getDaxiao, postDaxiao, getShengping, postShengping, getZhenfu, postZhenfu, getJunzhi, postJunzhi } from '../api'
import NumberBalls from '../components/NumberBalls.vue'
import NumberPad from '../components/NumberPad.vue'
import TrendChart from '../components/TrendChart.vue'
import AppIcon from '../components/AppIcon.vue'

const ECHO_FIELDS = {
  ssq: { main: '01 02 03 04 05 06', special: '16', specialLabel: '蓝球', digit: false },
  dlt: { main: '05 11 19 28 33', special: '02 10', specialLabel: '后区', digit: false },
  qlc: { main: '03 08 12 18 21 25 29', special: '09', specialLabel: '特别号', digit: false },
  kl8: { main: '01 05 12 18 22 27', special: '', specialLabel: '', digit: false },
  fc3d: { main: '1 2 3', special: '', specialLabel: '', digit: true },
  pl3: { main: '1 2 3', special: '', specialLabel: '', digit: true },
  pl5: { main: '1 2 3 4 5', special: '', specialLabel: '', digit: true },
  qxc: { main: '1 2 3 4 5 6', special: '7', specialLabel: '特别号', digit: true },
}

const route = useRoute()
const type = ref(route.query.type || 'ssq')
const data = ref(null)
const shape = ref(null)
const draws = ref([])
const periods = ref(50)
const loading = ref(true)
const drawsLoading = ref(true)
const echoMain = ref('')
const echoSpecial = ref('')
const echoResult = ref(null)
const echoError = ref('')
const echoLoading = ref(false)
const affinity = ref(null)
const affinitySeed = ref('')
const affinityError = ref('')
const affinityLoading = ref(false)
let affinityToken = 0

const COLLISION_FIELDS = {
  ssq: {
    digit: false,
    main: { from: 1, to: 33, pad: 2, max: 20, color: 'red', label: '红球' },
    special: { from: 1, to: 16, pad: 2, max: 16, color: 'blue', label: '蓝球' },
  },
  dlt: {
    digit: false,
    main: { from: 1, to: 35, pad: 2, max: 20, color: 'red', label: '前区' },
    special: { from: 1, to: 12, pad: 2, max: 12, color: 'blue', label: '后区' },
  },
  qlc: {
    digit: false,
    main: { from: 1, to: 30, pad: 2, max: 16, color: 'red', label: '基本号' },
    special: { from: 1, to: 30, pad: 2, max: 1, color: 'blue', label: '特别号' },
  },
  kl8: {
    digit: false,
    main: { from: 1, to: 80, pad: 2, max: 20, color: 'orange', label: '号码' },
    special: null,
  },
  fc3d: { digit: true, positions: ['百', '十', '个'], hi: 9, special: null },
  pl3: { digit: true, positions: ['百', '十', '个'], hi: 9, special: null },
  pl5: { digit: true, positions: ['万', '千', '百', '十', '个'], hi: 9, special: null },
  qxc: {
    digit: true,
    positions: ['1', '2', '3', '4', '5', '6'],
    hi: 9,
    special: { from: 0, to: 14, pad: 1, max: 1, color: 'orange', label: '特别号' },
  },
}

let collisionKey = 0
function blankCollisionTicket() {
  collisionKey += 1
  const field = COLLISION_FIELDS[type.value] || COLLISION_FIELDS.ssq
  return {
    key: collisionKey,
    mainText: '',
    specialText: '',
    digits: field.digit ? field.positions.map(() => '') : [],
  }
}

const echoField = computed(() => ECHO_FIELDS[type.value] || ECHO_FIELDS.ssq)
const collisionField = computed(() => COLLISION_FIELDS[type.value] || COLLISION_FIELDS.ssq)
const collisionTickets = ref([blankCollisionTicket(), blankCollisionTicket()])
const collisionPaste = ref('')
const collisionResult = ref(null)
const collisionError = ref('')
const collisionLoading = ref(false)
const collisionUsePad = ref(false)
const repeatMain = ref('')
const repeatSpecial = ref('')
const repeatPulse = ref(null)
const repeatScore = ref(null)
const repeatError = ref('')
const repeatLoading = ref(false)
const repeatPulseLoading = ref(false)
let repeatToken = 0
const REPEAT_LIMIT = 80
const momentumShort = ref(10)
const momentumLong = ref(50)
const momentumMain = ref('')
const momentumSpecial = ref('')
const momentum = ref(null)
const momentumScore = ref(null)
const momentumError = ref('')
const momentumLoading = ref(false)
const momentumBoardLoading = ref(false)
let momentumToken = 0
const neighborLimit = ref(80)
const neighborHorizon = ref(3)
const neighborMain = ref('')
const neighborSpecial = ref('')
const neighbor = ref(null)
const neighborScore = ref(null)
const neighborError = ref('')
const neighborLoading = ref(false)
const neighborBoardLoading = ref(false)
let neighborToken = 0
const spanLimit = ref(80)
const spanShort = ref(10)
const spanLong = ref(50)
const spanMain = ref('')
const spanSpecial = ref('')
const span = ref(null)
const spanScore = ref(null)
const spanError = ref('')
const spanLoading = ref(false)
const spanBoardLoading = ref(false)
let spanToken = 0
const clusterLimit = ref(80)
const clusterShort = ref(10)
const clusterLong = ref(50)
const clusterMain = ref('')
const clusterSpecial = ref('')
const cluster = ref(null)
const clusterScore = ref(null)
const clusterError = ref('')
const clusterLoading = ref(false)
const clusterBoardLoading = ref(false)
let clusterToken = 0
const roadLimit = ref(80)
const roadShort = ref(10)
const roadLong = ref(50)
const roadMain = ref('')
const roadSpecial = ref('')
const road = ref(null)
const roadScore = ref(null)
const roadError = ref('')
const roadLoading = ref(false)
const roadBoardLoading = ref(false)
let roadToken = 0
const sumLimit = ref(80)
const sumShort = ref(10)
const sumLong = ref(50)
const sumMain = ref('')
const sumSpecial = ref('')
const sumPulse = ref(null)
const sumScore = ref(null)
const sumError = ref('')
const sumLoading = ref(false)
const sumBoardLoading = ref(false)
let sumToken = 0
const parityLimit = ref(80)
const parityShort = ref(10)
const parityLong = ref(50)
const parityMain = ref('')
const paritySpecial = ref('')
const parity = ref(null)
const parityScore = ref(null)
const parityError = ref('')
const parityLoading = ref(false)
const parityBoardLoading = ref(false)
let parityToken = 0
const primeLimit = ref(80)
const primeShort = ref(10)
const primeLong = ref(50)
const primeMain = ref('')
const primeSpecial = ref('')
const prime = ref(null)
const primeScore = ref(null)
const primeError = ref('')
const primeLoading = ref(false)
const primeBoardLoading = ref(false)
let primeToken = 0
const zoneLimit = ref(80)
const zoneShort = ref(10)
const zoneLong = ref(50)
const zoneMain = ref('')
const zoneSpecial = ref('')
const zone = ref(null)
const zoneScore = ref(null)
const zoneError = ref('')
const zoneLoading = ref(false)
const zoneBoardLoading = ref(false)
let zoneToken = 0
const tailLimit = ref(80)
const tailShort = ref(10)
const tailLong = ref(50)
const tailMain = ref('')
const tailSpecial = ref('')
const tail = ref(null)
const tailScore = ref(null)
const tailError = ref('')
const tailLoading = ref(false)
const tailBoardLoading = ref(false)
let tailToken = 0
const acLimit = ref(80)
const acShort = ref(10)
const acLong = ref(50)
const acMain = ref('')
const acSpecial = ref('')
const acPulse = ref(null)
const acScore = ref(null)
const acError = ref('')
const acLoading = ref(false)
const acBoardLoading = ref(false)
let acToken = 0
const heweiLimit = ref(80)
const heweiShort = ref(10)
const heweiLong = ref(50)
const heweiMain = ref('')
const heweiSpecial = ref('')
const heweiPulse = ref(null)
const heweiScore = ref(null)
const heweiError = ref('')
const heweiLoading = ref(false)
const heweiBoardLoading = ref(false)
let heweiToken = 0
const daxiaoLimit = ref(80)
const daxiaoShort = ref(10)
const daxiaoLong = ref(50)
const daxiaoMain = ref('')
const daxiaoSpecial = ref('')
const daxiao = ref(null)
const daxiaoScore = ref(null)
const daxiaoError = ref('')
const daxiaoLoading = ref(false)
const daxiaoBoardLoading = ref(false)
let daxiaoToken = 0
const shengpingLimit = ref(80)
const shengpingShort = ref(10)
const shengpingLong = ref(50)
const shengpingMain = ref('')
const shengpingSpecial = ref('')
const shengping = ref(null)
const shengpingScore = ref(null)
const shengpingError = ref('')
const shengpingLoading = ref(false)
const shengpingBoardLoading = ref(false)
let shengpingToken = 0
const zhenfuLimit = ref(80)
const zhenfuShort = ref(10)
const zhenfuLong = ref(50)
const zhenfuMain = ref('')
const zhenfuSpecial = ref('')
const zhenfu = ref(null)
const zhenfuScore = ref(null)
const zhenfuError = ref('')
const zhenfuLoading = ref(false)
const zhenfuBoardLoading = ref(false)
let zhenfuToken = 0
const junzhiLimit = ref(80)
const junzhiShort = ref(10)
const junzhiLong = ref(50)
const junzhiMain = ref('')
const junzhiSpecial = ref('')
const junzhi = ref(null)
const junzhiScore = ref(null)
const junzhiError = ref('')
const junzhiLoading = ref(false)
const junzhiBoardLoading = ref(false)
let junzhiToken = 0
const collisionMainHits = computed(() => (collisionResult.value?.number_hits || []).filter((item) => item.kind === 'main' && item.collision))
const collisionSpecialHits = computed(() => (collisionResult.value?.number_hits || []).filter((item) => item.kind === 'special' && item.collision))
const affinityDigit = computed(() => echoField.value.digit)
const affinityWindow = computed(() => Math.min(Math.max(periods.value, 50), 200))
const affinityHint = computed(() => (
  affinityDigit.value
    ? '只看不同位置。点一个数字，看其他位置经常一起开出什么。'
    : '主号不分先后。点一个球，看它开出时还经常带上谁。'
))
const affinityGroups = computed(() => {
  const groups = affinity.value?.companions || []
  if (affinity.value?.seed) return groups
  return groups.slice(0, 4).map((group) => ({
    ...group,
    companions: (group.companions || []).slice(0, 3),
  }))
})
const showSpecialShare = computed(() => Boolean(echoField.value.specialLabel))
const repeatHint = computed(() => (
  echoField.value.digit
    ? '同一位置数字相同才算重号，顺序不能打乱。仅供娱乐，不构成投注建议。'
    : '主号看和上一期重了几个，特别号单独算，不计入重号。仅供娱乐，不构成投注建议。'
))
const momentumHint = computed(() => (
  echoField.value.digit
    ? '按位置比较短窗和长窗出现率。差达到 2% 算升温，低到 -2% 算降温。特别号单独看。仅供娱乐，不构成投注建议。'
    : '短窗出现率减去长窗出现率。差达到 2% 算升温，低到 -2% 算降温。特别号单独看，不计入主号。仅供娱乐，不构成投注建议。'
))
const momentumThreshold = computed(() => {
  const value = Number(momentum.value?.threshold)
  if (!Number.isFinite(value)) return '2%'
  return `${Math.round(value * 1000) / 10}%`
})
const momentumRisingCount = computed(() => {
  const body = momentum.value
  if (!body) return 0
  if (body.mode === 'digit') return (body.positions || []).reduce((sum, pos) => sum + (pos.rising || []).length, 0)
  return (body.rising || []).length
})
const momentumFallingCount = computed(() => {
  const body = momentum.value
  if (!body) return 0
  if (body.mode === 'digit') return (body.positions || []).reduce((sum, pos) => sum + (pos.falling || []).length, 0)
  return (body.falling || []).length
})
const momentumScoreText = computed(() => {
  const score = momentumScore.value
  if (!score?.ticket) return ''
  const ticket = score.ticket
  let text = `主号升温 ${ticket.rising_count}、降温 ${ticket.falling_count}、持平 ${ticket.flat_count}，动量分 ${ticket.score}`
  const special = score.special_ticket
  const specialCount = (special?.rising_count || 0) + (special?.falling_count || 0) + (special?.flat_count || 0)
  if (specialCount) {
    text += `。特别号升温 ${special.rising_count}、降温 ${special.falling_count}、持平 ${special.flat_count}，不计入主号分`
  }
  return `${text}。仅供娱乐，不构成投注建议。`
})
const spanHint = computed(() => (
  echoField.value.digit
    ? '整注各位数字的最大减最小，0 和 9 不绕圈。特别号不计入主号。短窗平均比长窗高出 0.5 算变宽。仅供娱乐，不构成投注建议。'
    : '主号里最大号减去最小号，特别号不计入。有两个及以上特别号时另看它们的跨度。短窗平均比长窗高出 0.5 算变宽。仅供娱乐，不构成投注建议。'
))
const spanBars = computed(() => spanVisibleBars(span.value?.distribution))
const spanBarsCollapsed = computed(() => {
  const rows = span.value?.distribution || []
  return spanBars.value.length < rows.length
})
const spanSpecialBars = computed(() => spanVisibleBars(span.value?.special?.distribution))
const spanSpecialScored = computed(() => spanScore.value?.special_ticket?.span != null)
const clusterHint = computed(() => (
  echoField.value.digit
    ? '按位从左到右，相邻位相差 1 算连号，0 和 9 不绕圈。没有连号时最长簇记为 1。短窗平均比长窗高出 0.5 算变长。仅供娱乐，不构成投注建议。'
    : '主号去重后，挨在一起的号码算一簇，特别号不并进去。有两个及以上特别号时另看它们的连号簇。没有连号时最长簇记为 1。短窗平均比长窗高出 0.5 算变长。仅供娱乐，不构成投注建议。'
))
const clusterBars = computed(() => pulseVisibleBars(cluster.value?.distribution, 'max_len'))
const clusterBarsCollapsed = computed(() => {
  const rows = cluster.value?.distribution || []
  return clusterBars.value.length < rows.length
})
const clusterCountBars = computed(() => pulseVisibleBars(cluster.value?.cluster_counts?.distribution, 'clusters'))
const clusterSpecialBars = computed(() => pulseVisibleBars(cluster.value?.special?.distribution, 'max_len'))
const clusterSpecialScored = computed(() => clusterScore.value?.special_ticket?.max_len != null)
const roadHint = computed(() => (
  echoField.value.digit
    ? '整注各位数字除以 3 的余数是 0路、1路或 2路，0 和 9 不绕圈。路偏度是最多的一路减去最少的一路。特别号不计入主号。短窗平均比长窗高出 0.5 算更偏。仅供娱乐，不构成投注建议。'
    : '主号去重后按除以 3 的余数分成 0路、1路、2路，特别号不并进去。有特别号时另看它们的路。路偏度是最多的一路减去最少的一路。短窗平均比长窗高出 0.5 算更偏。仅供娱乐，不构成投注建议。'
))
const roadBars = computed(() => pulseVisibleBars(road.value?.distribution, 'imbalance'))
const roadBarsCollapsed = computed(() => {
  const rows = road.value?.distribution || []
  return roadBars.value.length < rows.length
})
const roadSpecialBars = computed(() => pulseVisibleBars(road.value?.special?.distribution, 'imbalance'))
const roadSpecialScored = computed(() => roadScore.value?.special_ticket?.imbalance != null)
const sumHint = computed(() => (
  echoField.value.digit
    ? '整注各位数字相加，0 和 9 不绕圈。特别号不计入主号和值。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
    : '主号去重后各号相加，特别号不计入。有两个及以上特别号时另看它们的和值。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
))
const sumBars = computed(() => pulseVisibleBars(sumPulse.value?.distribution, 'sum'))
const sumBarsCollapsed = computed(() => {
  const rows = sumPulse.value?.distribution || []
  return sumBars.value.length < rows.length
})
const sumSpecialBars = computed(() => pulseVisibleBars(sumPulse.value?.special?.distribution, 'sum'))
const sumSpecialScored = computed(() => sumScore.value?.special_ticket?.sum != null)
const parityHint = computed(() => (
  echoField.value.digit
    ? '整注各位数字里数奇数，0 是偶数，9 是奇数，不绕圈。特别号不计入主号。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
    : '主号去重后数有几个奇数，特别号不计入。有两个及以上特别号时另看它们的奇数个数。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
))
const parityBars = computed(() => pulseVisibleBars(parity.value?.distribution, 'odd_count'))
const parityBarsCollapsed = computed(() => {
  const rows = parity.value?.distribution || []
  return parityBars.value.length < rows.length
})
const paritySpecialBars = computed(() => pulseVisibleBars(parity.value?.special?.distribution, 'odd_count'))
const paritySpecialScored = computed(() => parityScore.value?.special_ticket?.odd_count != null)
const primeHint = computed(() => (
  echoField.value.digit
    ? '整注各位数字里数质数，1、2、3、5、7 是质，0、4、6、8、9 是合，不绕圈。特别号不计入主号。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
    : '主号去重后数有几个质数，1 也算质数，特别号不计入。有两个及以上特别号时另看它们的质数个数。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
))
const primeBars = computed(() => pulseVisibleBars(prime.value?.distribution, 'prime_count'))
const primeBarsCollapsed = computed(() => {
  const rows = prime.value?.distribution || []
  return primeBars.value.length < rows.length
})
const primeSpecialBars = computed(() => pulseVisibleBars(prime.value?.special?.distribution, 'prime_count'))
const primeSpecialScored = computed(() => primeScore.value?.special_ticket?.prime_count != null)
const zoneHint = computed(() => (
  echoField.value.digit
    ? '整注各位数字分成低区 0–3、中区 4–6、高区 7–9，0 和 9 不绕圈。区位偏度是最多的一区减去最少的一区。特别号不计入主号。短窗平均比长窗高出 0.5 算更偏。仅供娱乐，不构成投注建议。'
    : '主号去重后按数值区间分成三区，不是除以 3 的余数。特别号不并进去，有特别号时按它自己的区间另看。区位偏度是最多的一区减去最少的一区。短窗平均比长窗高出 0.5 算更偏。仅供娱乐，不构成投注建议。'
))
const zoneBars = computed(() => pulseVisibleBars(zone.value?.distribution, 'imbalance'))
const zoneBarsCollapsed = computed(() => {
  const rows = zone.value?.distribution || []
  return zoneBars.value.length < rows.length
})
const zoneSpecialBars = computed(() => pulseVisibleBars(zone.value?.special?.distribution, 'imbalance'))
const zoneSpecialScored = computed(() => zoneScore.value?.special_ticket?.imbalance != null)
const tailHint = computed(() => (
  echoField.value.digit
    ? '整注各位数字本身就是尾数，种类是不重复的数字个数，0 和 9 不绕圈。特别号不计入主号。短窗平均比长窗高出 0.5 算更散。仅供娱乐，不构成投注建议。'
    : '主号去重后取个位，同一尾数只算一种，不是 012 路，也不是区位、跨度或和值。特别号不并进去。短窗平均比长窗高出 0.5 算更散。仅供娱乐，不构成投注建议。'
))
const tailBars = computed(() => pulseVisibleBars(tail.value?.distribution, 'unique_tail_count'))
const tailBarsCollapsed = computed(() => {
  const rows = tail.value?.distribution || []
  return tailBars.value.length < rows.length
})
const tailSpecialBars = computed(() => pulseVisibleBars(tail.value?.special?.distribution, 'unique_tail_count'))
const tailSpecialScored = computed(() => tailScore.value?.special_ticket?.unique_tail_count != null)
const acHint = computed(() => (
  echoField.value.digit
    ? '整注各位数字从小到大排列，两两绝对差去重后再减去位数减一，0 和 9 不绕圈。少于两位不算。特别号不计入主号。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
    : '主号去重后从小到大排列，两两绝对差去重后再减去号码个数减一。少于两个主号不算，不记成 0。特别号不并进去，至少两个特别号才另算。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
))
const acBars = computed(() => pulseVisibleBars(acPulse.value?.distribution, 'ac_value'))
const acBarsCollapsed = computed(() => {
  const rows = acPulse.value?.distribution || []
  return acBars.value.length < rows.length
})
const acSpecialBars = computed(() => pulseVisibleBars(acPulse.value?.special?.distribution, 'ac_value'))
const acSpecialScored = computed(() => acScore.value?.special_ticket?.ac_value != null)
const heweiHint = computed(() => (
  echoField.value.digit
    ? '整注各位数字相加后取个位，重复数字保留，0 和 9 不绕圈。这不是原始和值，也不是不重复尾数的种类数。特别号不计入主号。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
    : '主号去重后相加，取和值的个位。这不是原始和值，也不是尾数种类。特别号不并进去，有特别号时另算。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
))
const heweiBars = computed(() => pulseVisibleBars(heweiPulse.value?.distribution, 'hewei'))
const heweiSpecialBars = computed(() => pulseVisibleBars(heweiPulse.value?.special?.distribution, 'hewei'))
const heweiSpecialScored = computed(() => heweiScore.value?.special_ticket?.hewei != null)
const daxiaoHint = computed(() => {
  const boundary = daxiao.value?.boundary
  if (echoField.value.digit) {
    return '整注各位数字里，0–4 为小、5–9 为大，重复数字保留。特别号不计入主号。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
  }
  if (boundary) {
    return `主号去重后，${boundary.lo}–${boundary.mid} 为小、${boundary.mid + 1}–${boundary.hi} 为大。特别号另算。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。`
  }
  return '主号按号码池中点分大小，大于中点为大。特别号另算。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
})
const daxiaoBars = computed(() => pulseVisibleBars(daxiao.value?.distribution, 'big_count'))
const daxiaoSpecialBars = computed(() => pulseVisibleBars(daxiao.value?.special?.distribution, 'big_count'))
const daxiaoSpecialScored = computed(() => daxiaoScore.value?.special_ticket?.big_count != null)
const shengpingHint = computed(() => (
  echoField.value.digit
    ? '按位比较相邻两期，保留重复和位置，不排序。当期位更大为升、相等为平、更小为降。特别号不计入主号。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
    : '主号去重后升序，按该彩种标准个数逐位比较。号码不足的期跳过。特别号另算，不并进主号。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
))
const shengpingBars = computed(() => pulseVisibleBars(shengping.value?.distribution, 'rise_count'))
const shengpingSpecialBars = computed(() => pulseVisibleBars(shengping.value?.special?.distribution, 'rise_count'))
const shengpingSpecialScored = computed(() => shengpingScore.value?.special_ticket?.rise_count != null)
const zhenfuHint = computed(() => (
  echoField.value.digit
    ? '按位比较相邻两期，保留重复和位置，不排序。振幅是各位绝对差之和，0 与 9 不绕圈。特别号不计入主号。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
    : '主号去重后升序，按该彩种标准个数逐位比较绝对差。号码不足的期跳过。特别号另算，不并进主号。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
))
const zhenfuBars = computed(() => pulseVisibleBars(zhenfu.value?.distribution, 'amplitude_sum'))
const zhenfuSpecialBars = computed(() => pulseVisibleBars(zhenfu.value?.special?.distribution, 'amplitude_sum'))
const zhenfuSpecialScored = computed(() => zhenfuScore.value?.special_ticket?.amplitude_sum != null)
const junzhiHint = computed(() => (
  echoField.value.digit
    ? '按抽出的各位取算术平均，保留重复和位置，不排序。均值保留两位小数。特别号不计入主号。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
    : '主号去重后取算术平均，重复只算一次。特别号另算，不并进主号。短窗平均比长窗高出 0.5 算走高。仅供娱乐，不构成投注建议。'
))
const junzhiBars = computed(() => pulseVisibleBars(junzhi.value?.distribution, 'mean_value'))
const junzhiSpecialBars = computed(() => pulseVisibleBars(junzhi.value?.special?.distribution, 'mean_value'))
const junzhiSpecialScored = computed(() => junzhiScore.value?.special_ticket?.mean_value != null)
const neighborHint = computed(() => (
  echoField.value.digit
    ? '按位置看。某个数字开出后，随后几期同一位置会不会开出旁边的数字。0 和 9 不绕圈，特别号单独看。仅供娱乐，不构成投注建议。'
    : '某个主号开出后，随后几期会不会开出旁边的号。同期一起开出不算，号码自己重开也不算。特别号单独看。仅供娱乐，不构成投注建议。'
))
const neighborPullCount = computed(() => {
  const body = neighbor.value
  if (!body) return 0
  if (body.mode === 'digit') return (body.positions || []).reduce((sum, pos) => sum + (pos.pulled || []).length, 0)
  return (body.pulled || []).length
})
const neighborScoreText = computed(() => {
  const score = neighborScore.value
  if (!score?.ticket) return ''
  const ticket = score.ticket
  const strength = neighborSigned(ticket.strength)
  let text = `这注有 ${ticket.score} 个号挨着最近 ${score.horizon} 期开出的主号，牵引差合计 ${strength}`
  const special = score.special_ticket
  if ((special?.pulled_count || 0) + (special?.idle_count || 0) > 0) {
    text += `。特别号牵引 ${special.score} 个，不计入主号`
  }
  return `${text}。仅供娱乐，不构成投注建议。`
})
const neighborSpecialScored = computed(() => {
  const special = neighborScore.value?.special_ticket
  if (!special) return false
  return (special.pulled_count || 0) + (special.idle_count || 0) > 0
})
const neighborScoreView = computed(() => {
  const score = neighborScore.value
  if (!score?.query) return { numbers: { main: [], special: [] }, marks: null }
  const items = score.ticket?.items || []
  if (score.mode === 'digit') {
    const positions = items.map((item) => [item.number])
    const marks = items.map((item) => [Boolean(item.pulled)])
    if ((score.query.special || []).length) {
      const shared = new Set(score.special_ticket?.pulled || [])
      positions.push(score.query.special)
      marks.push(score.query.special.map((n) => shared.has(String(n))))
    }
    return { numbers: { positions }, marks: { positions: marks } }
  }
  const shared = new Set(score.ticket?.pulled || [])
  const sharedSpecial = new Set(score.special_ticket?.pulled || [])
  return {
    numbers: { main: score.query.main, special: score.query.special },
    marks: {
      main: (score.query.main || []).map((n) => shared.has(String(n))),
      special: (score.query.special || []).map((n) => sharedSpecial.has(String(n))),
    },
  }
})
const momentumSpecialScored = computed(() => {
  const special = momentumScore.value?.special_ticket
  if (!special) return false
  return (special.rising_count || 0) + (special.falling_count || 0) + (special.flat_count || 0) > 0
})
const repeatRecent = computed(() => (repeatPulse.value?.recent_pairs || []).slice(0, 8))
const repeatSummary = computed(() => {
  const score = repeatScore.value
  if (!score) return ''
  if (score.message) return `${score.message}。仅供娱乐，不构成投注建议。`
  const fresh = (score.fresh_main || []).length
  let text = `这注重号 ${score.overlap} 个，新号 ${fresh} 个`
  if (score.special_overlap) text += `，特别号重了 ${score.special_overlap} 个，不计入主号`
  if (score.percentile == null) {
    text += '。相邻样本还不够，看不出这注排在哪里'
  } else {
    const pct = Math.round(Number(score.percentile) * 100)
    const heavier = Math.max(0, Number(score.rank || 1) - 1)
    text += `。近 ${score.pair_count} 次相邻交接里，${pct}% 的重号个数不超过这次，有 ${heavier} 次更重`
  }
  return `${text}。仅供娱乐，不构成投注建议。`
})
const repeatScoreView = computed(() => {
  const score = repeatScore.value
  if (!score?.query) return { numbers: { main: [], special: [] }, marks: null }
  if (score.mode === 'digit') {
    const positions = (score.positions || []).map((pos) => [pos.ticket])
    const marks = (score.positions || []).map((pos) => [Boolean(pos.repeat)])
    if ((score.query.special || []).length) {
      const shared = new Set(score.repeat_special || [])
      positions.push(score.query.special)
      marks.push(score.query.special.map((n) => shared.has(String(n))))
    }
    return { numbers: { positions }, marks: { positions: marks } }
  }
  const shared = new Set(score.repeat_main || [])
  const sharedSpecial = new Set(score.repeat_special || [])
  return {
    numbers: { main: score.query.main, special: score.query.special },
    marks: {
      main: (score.query.main || []).map((n) => shared.has(String(n))),
      special: (score.query.special || []).map((n) => sharedSpecial.has(String(n))),
    },
  }
})

const displayFreq = computed(() => {
  if (!data.value) return []
  const arr = data.value.main_freq || []
  if (arr.length > 40) return arr.filter((_, i) => i % 2 === 0).slice(0, 40)
  return arr.slice(0, 33)
})

const heatGrid = computed(() => {
  const n = data.value?.heatmap?.length || 11
  const cols = n > 40 ? 10 : n > 20 ? 11 : Math.min(10, n)
  return { gridTemplateColumns: `repeat(${cols}, 1fr)` }
})

const omitRows = computed(() => {
  const list = data.value?.main_omit || []
  const rows = []
  for (let i = 0; i < list.length; i += 3) {
    const chunk = list.slice(i, i + 3)
    const cells = []
    chunk.forEach((c) => { cells.push(c.n, c.omit) })
    while (cells.length < 6) cells.push('', '')
    rows.push(cells)
  }
  return rows.slice(0, 15)
})

function barH(c) {
  const mx = Math.max(...displayFreq.value.map((f) => f.count), 1)
  return Math.max(4, Math.round((c / mx) * 100))
}

async function loadDraws() {
  drawsLoading.value = true
  try {
    const history = await api.draws(type.value, 300)
    draws.value = history.items || []
  } catch (e) {
    console.error(e)
    draws.value = []
  } finally {
    drawsLoading.value = false
  }
}

async function loadAnalysis() {
  loading.value = true
  const limit = Math.max(periods.value, 50)
  try {
    const [analysis, shapeRes] = await Promise.all([
      api.analysis(type.value, limit),
      api.shape(type.value, limit).catch((e) => {
        console.error(e)
        return null
      }),
    ])
    data.value = analysis
    shape.value = shapeRes
  } catch (e) {
    console.error(e)
    data.value = null
    shape.value = null
  } finally {
    loading.value = false
  }
}

function splitNums(text) {
  return String(text || '').trim().split(/[\s,，]+/).filter(Boolean)
}

function echoMarks(row) {
  const query = echoResult.value?.query
  if (!query) return null
  const specialSet = new Set(row.shared_special || [])
  if (echoResult.value.mode === 'digit') {
    return {
      main: (row.main || []).map((n, i) => (n === query.main[i] ? true : null)),
      special: (row.special || []).map((n) => (specialSet.has(n) ? true : null)),
    }
  }
  const mainSet = new Set(row.shared_main || [])
  return {
    main: (row.main || []).map((n) => (mainSet.has(n) ? true : null)),
    special: (row.special || []).map((n) => (specialSet.has(n) ? true : null)),
  }
}

async function runEcho() {
  echoLoading.value = true
  echoError.value = ''
  try {
    const main = splitNums(echoMain.value)
    const special = echoField.value.specialLabel ? splitNums(echoSpecial.value) : []
    echoResult.value = await api.echo(type.value, { main, special, limit: 80, top: 8 })
  } catch (e) {
    echoResult.value = null
    echoError.value = e.message || '对照失败'
  } finally {
    echoLoading.value = false
  }
}

async function fillLatestEcho() {
  echoError.value = ''
  try {
    const history = await api.draws(type.value, 1)
    const latest = history.items?.[0]
    if (!latest) {
      echoResult.value = null
      echoError.value = '暂无开奖可对照'
      return
    }
    echoMain.value = (latest.numbers?.main || []).join(' ')
    echoSpecial.value = (latest.numbers?.special || []).join(' ')
    await runEcho()
  } catch (e) {
    echoError.value = e.message || '读取开奖失败'
  }
}

function affinityRate(rate) {
  const value = Number(rate)
  if (!Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function affinityKey(item) {
  return `${item.position ?? ''}-${item.n}`
}

function pairKey(pair) {
  return `${pair.pos_a ?? ''}-${pair.a}-${pair.pos_b ?? ''}-${pair.b}`
}

function specialKey(row) {
  return `${row.position ?? ''}-${row.main || row.n}-${row.special}`
}

function pickAffinitySeed(n) {
  affinitySeed.value = String(n ?? '')
  loadAffinity()
}

function clearAffinitySeed() {
  affinitySeed.value = ''
  loadAffinity()
}

async function loadAffinity() {
  const token = ++affinityToken
  affinityLoading.value = true
  affinityError.value = ''
  const seed = affinitySeed.value.trim()
  try {
    const body = await api.affinity(type.value, { limit: affinityWindow.value, seed: seed || undefined })
    if (token !== affinityToken) return
    affinity.value = body
    affinitySeed.value = body.seed || ''
  } catch (e) {
    if (token !== affinityToken) return
    affinity.value = null
    affinityError.value = e.message || '结伴加载失败'
  } finally {
    if (token === affinityToken) affinityLoading.value = false
  }
}

function fillCollisionDigits(ticket) {
  const field = collisionField.value
  if (!field.digit) {
    ticket.digits = []
    return
  }
  const parts = splitNums(ticket.mainText)
  ticket.digits = field.positions.map((_, index) => parts[index] || '')
}

function toggleCollisionPad() {
  if (!collisionUsePad.value) {
    collisionTickets.value.forEach(fillCollisionDigits)
  } else if (collisionField.value.digit) {
    collisionTickets.value.forEach((ticket) => {
      ticket.mainText = (ticket.digits || []).join(' ').trim()
    })
  }
  collisionUsePad.value = !collisionUsePad.value
}

function setCollisionDigit(ticket, index, selected) {
  if (!ticket.digits.length) fillCollisionDigits(ticket)
  ticket.digits[index] = selected[0] || ''
  ticket.mainText = ticket.digits.join(' ').trim()
}

function addCollisionTicket() {
  if (collisionTickets.value.length >= 20) return
  collisionTickets.value.push(blankCollisionTicket())
}

function removeCollisionTicket(index) {
  if (collisionTickets.value.length <= 2) return
  collisionTickets.value.splice(index, 1)
}

function collisionPayload(ticket) {
  const field = collisionField.value
  const main = field.digit && collisionUsePad.value
    ? (ticket.digits || []).filter((item) => item !== '')
    : splitNums(ticket.mainText)
  const special = field.special ? splitNums(ticket.specialText) : []
  return { main, special }
}

function collisionPosLabel(index) {
  return collisionField.value.positions?.[index] || String(index + 1)
}

function collisionScope(result) {
  if (result?.message) return '购彩记录'
  if (result?.source === 'records' && result.record_scope === 'open') return '未开奖的购彩记录'
  if (result?.source === 'records') return '最近的购彩记录'
  return '手填号码'
}

function collisionNumbers(ticket) {
  if (collisionResult.value?.mode !== 'digit') {
    return { main: ticket.main, special: ticket.special }
  }
  const positions = (ticket.main || []).map((n) => [n])
  if ((ticket.special || []).length) positions.push([ticket.special[0]])
  return { positions }
}

function collisionMarks(ticket) {
  const hits = collisionResult.value?.number_hits || []
  if (collisionResult.value?.mode === 'digit') {
    const positions = (ticket.main || []).map((n, index) => {
      const hit = hits.find((item) => item.kind === 'main' && item.position === index && item.n === String(n))
      return [hit && hit.count >= 2 ? hit.count : null]
    })
    if ((ticket.special || []).length) {
      const hit = hits.find((item) => item.kind === 'special' && item.n === String(ticket.special[0]))
      positions.push([hit && hit.count >= 2 ? hit.count : null])
    }
    return { positions }
  }
  const mainCount = new Map(hits.filter((item) => item.kind === 'main').map((item) => [item.n, item.count]))
  const specialCount = new Map(hits.filter((item) => item.kind === 'special').map((item) => [item.n, item.count]))
  return {
    main: (ticket.main || []).map((n) => ((mainCount.get(String(n)) || 0) >= 2 ? mainCount.get(String(n)) : null)),
    special: (ticket.special || []).map((n) => ((specialCount.get(String(n)) || 0) >= 2 ? specialCount.get(String(n)) : null)),
  }
}

function repeatStat(value) {
  if (value == null || value === '') return '—'
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return String(Math.round(num * 100) / 100)
}

function repeatBarWidth(count) {
  const rows = repeatPulse.value?.distribution || []
  const max = Math.max(...rows.map((row) => row.count), 1)
  if (!count) return '0%'
  return `${Math.max(8, Math.round((count / max) * 100))}%`
}

function repeatPairNumbers(pair) {
  if (repeatPulse.value?.mode === 'digit') {
    const positions = (pair.positions || []).map((pos) => [pos.to || ''])
    if ((pair.special || []).length) positions.push(pair.special)
    return { positions }
  }
  return { main: pair.main, special: pair.special }
}

function repeatPairMarks(pair) {
  if (repeatPulse.value?.mode === 'digit') {
    const positions = (pair.positions || []).map((pos) => [Boolean(pos.repeat)])
    if ((pair.special || []).length) {
      const shared = new Set(pair.shared_special || [])
      positions.push(pair.special.map((n) => shared.has(String(n))))
    }
    return { positions }
  }
  const shared = new Set(pair.shared_main || [])
  const sharedSpecial = new Set(pair.shared_special || [])
  return {
    main: (pair.main || []).map((n) => shared.has(String(n))),
    special: (pair.special || []).map((n) => sharedSpecial.has(String(n))),
  }
}

async function loadRepeat() {
  const token = ++repeatToken
  repeatPulseLoading.value = true
  try {
    const body = await api.repeat(type.value, REPEAT_LIMIT)
    if (token !== repeatToken) return
    repeatPulse.value = body
  } catch (e) {
    if (token !== repeatToken) return
    repeatPulse.value = null
    repeatError.value = e.message || '脉搏加载失败'
  } finally {
    if (token === repeatToken) repeatPulseLoading.value = false
  }
}

async function runRepeat() {
  repeatLoading.value = true
  repeatError.value = ''
  try {
    const main = splitNums(repeatMain.value)
    const special = echoField.value.specialLabel ? splitNums(repeatSpecial.value) : []
    repeatScore.value = await api.repeatScore(type.value, { main, special, limit: REPEAT_LIMIT })
  } catch (e) {
    repeatScore.value = null
    repeatError.value = e.message || '对照失败'
  } finally {
    repeatLoading.value = false
  }
}

function momentumWindows() {
  let short = Math.round(Number(momentumShort.value))
  let long = Math.round(Number(momentumLong.value))
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  momentumShort.value = short
  momentumLong.value = long
  return { limit: 80, short, long }
}

function momentumStat(rows, number) {
  return (rows || []).find((item) => item.number === String(number))
}

function momentumTip(row) {
  if (!row) return ''
  const sign = row.delta > 0 ? '+' : ''
  const pct = (value) => `${(Number(value) * 100).toFixed(1)}%`
  return `短窗 ${pct(row.rate_short)} · 长窗 ${pct(row.rate_long)} · 差 ${sign}${row.delta}`
}

function momentumMemberLabel(item) {
  return item && typeof item === 'object' ? item.number : item
}

function momentumMemberTitle(item) {
  return item && typeof item === 'object' ? item.label : ''
}

function momentumMemberKey(item, index) {
  if (item && typeof item === 'object') return `${item.index}-${item.number}`
  return `${index}-${item}`
}

async function loadMomentum() {
  const token = ++momentumToken
  momentumBoardLoading.value = true
  const windows = momentumWindows()
  try {
    const body = await getMomentum(type.value, windows)
    if (token !== momentumToken) return
    momentum.value = body
    momentumScore.value = null
    momentumError.value = ''
  } catch (e) {
    if (token !== momentumToken) return
    momentum.value = null
    momentumScore.value = null
    momentumError.value = e.message || '动量加载失败'
  } finally {
    if (token === momentumToken) momentumBoardLoading.value = false
  }
}

async function runMomentum() {
  momentumLoading.value = true
  momentumError.value = ''
  const windows = momentumWindows()
  try {
    const main = splitNums(momentumMain.value)
    const special = echoField.value.specialLabel ? splitNums(momentumSpecial.value) : []
    const body = await postMomentum(type.value, { main, special, ...windows })
    momentum.value = body
    momentumScore.value = body
  } catch (e) {
    momentumScore.value = null
    momentumError.value = e.message || '打分失败'
  } finally {
    momentumLoading.value = false
  }
}

function neighborWindow() {
  let limit = Math.round(Number(neighborLimit.value))
  let horizon = Math.round(Number(neighborHorizon.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(horizon)) horizon = 3
  limit = Math.min(200, Math.max(5, limit))
  horizon = Math.min(10, Math.max(1, horizon))
  neighborLimit.value = limit
  neighborHorizon.value = horizon
  return { limit, horizon }
}

function neighborTop(rows, count = 8) {
  return (rows || []).slice(0, count)
}

function neighborSigned(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  const text = number.toFixed(4)
  return number > 0 ? `+${text}` : text
}

function neighborTip(edge) {
  if (!edge) return ''
  return `来自 ${edge.source} · 随后出现 ${edge.hits}/${edge.opportunities} · 比基线 ${neighborSigned(edge.lift)}。仅供娱乐，不构成投注建议。`
}

async function loadNeighbor() {
  const token = ++neighborToken
  neighborBoardLoading.value = true
  const params = neighborWindow()
  try {
    const body = await getNeighbor(type.value, params)
    if (token !== neighborToken) return
    neighbor.value = body
    neighborScore.value = null
    neighborError.value = ''
  } catch (e) {
    if (token !== neighborToken) return
    neighbor.value = null
    neighborScore.value = null
    neighborError.value = e.message || '牵引加载失败'
  } finally {
    if (token === neighborToken) neighborBoardLoading.value = false
  }
}

async function runNeighbor() {
  neighborLoading.value = true
  neighborError.value = ''
  const params = neighborWindow()
  try {
    const main = splitNums(neighborMain.value)
    const special = echoField.value.specialLabel ? splitNums(neighborSpecial.value) : []
    const body = await postNeighbor(type.value, { main, special, ...params })
    neighbor.value = body
    neighborScore.value = body
  } catch (e) {
    neighborScore.value = null
    neighborError.value = e.message || '打分失败'
  } finally {
    neighborLoading.value = false
  }
}

function spanWindows() {
  let limit = Math.round(Number(spanLimit.value))
  let short = Math.round(Number(spanShort.value))
  let long = Math.round(Number(spanLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  spanLimit.value = limit
  spanShort.value = short
  spanLong.value = long
  return { limit, short, long }
}

function spanVisibleBars(rows) {
  const list = rows || []
  if (list.length < 2) return list
  const lo = list[0].span
  const hi = list[list.length - 1].span
  if (hi - lo > 28) return list.filter((row) => row.count > 0)
  return list
}

function spanStat(value) {
  if (value == null || value === '') return '—'
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return String(Math.round(num * 100) / 100)
}

function spanSigned(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  const text = String(Math.round(number * 100) / 100)
  return number > 0 ? `+${text}` : text
}

function spanBarWidth(count, rows) {
  const max = Math.max(...(rows || []).map((row) => row.count), 1)
  if (!count) return '0%'
  return `${Math.max(8, Math.round((count / max) * 100))}%`
}

function spanDriftLabel(drift) {
  if (drift === 'rising') return '变宽'
  if (drift === 'falling') return '变窄'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function spanRarityLabel(rarity) {
  if (rarity === 'common') return '常见'
  if (rarity === 'typical') return '居中'
  if (rarity === 'rare') return '少见'
  return '暂无对照'
}

function spanAlignLabel(alignment) {
  if (alignment === 'aligned') return '顺着脉动'
  if (alignment === 'against') return '逆着脉动'
  if (alignment === 'neutral') return '脉动持平'
  return ''
}

function spanCurrent(value) {
  return spanScore.value?.ticket?.span === value
}

async function loadSpan() {
  const token = ++spanToken
  spanBoardLoading.value = true
  const params = spanWindows()
  try {
    const body = await getSpan(type.value, params)
    if (token !== spanToken) return
    span.value = body
    spanScore.value = null
    spanError.value = ''
  } catch (e) {
    if (token !== spanToken) return
    span.value = null
    spanScore.value = null
    spanError.value = e.message || '跨度加载失败'
  } finally {
    if (token === spanToken) spanBoardLoading.value = false
  }
}

async function runSpan() {
  spanLoading.value = true
  spanError.value = ''
  const params = spanWindows()
  try {
    const main = splitNums(spanMain.value)
    const special = echoField.value.specialLabel ? splitNums(spanSpecial.value) : []
    const body = await postSpan(type.value, { main, special, ...params })
    span.value = body
    spanScore.value = body
  } catch (e) {
    spanScore.value = null
    spanError.value = e.message || '打分失败'
  } finally {
    spanLoading.value = false
  }
}

function pulseVisibleBars(rows, key) {
  const list = rows || []
  if (list.length < 2) return list
  const lo = list[0][key]
  const hi = list[list.length - 1][key]
  if (hi - lo > 28) return list.filter((row) => row.count > 0)
  return list
}

function clusterWindows() {
  let limit = Math.round(Number(clusterLimit.value))
  let short = Math.round(Number(clusterShort.value))
  let long = Math.round(Number(clusterLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  clusterLimit.value = limit
  clusterShort.value = short
  clusterLong.value = long
  return { limit, short, long }
}

function clusterDriftLabel(drift) {
  if (drift === 'rising') return '变长'
  if (drift === 'falling') return '变短'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function clusterCountDriftLabel(drift) {
  if (drift === 'rising') return '变多'
  if (drift === 'falling') return '变少'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function clusterCurrent(value) {
  return clusterScore.value?.ticket?.max_len === value
}

async function loadCluster() {
  const token = ++clusterToken
  clusterBoardLoading.value = true
  const params = clusterWindows()
  try {
    const body = await getCluster(type.value, params)
    if (token !== clusterToken) return
    cluster.value = body
    clusterScore.value = null
    clusterError.value = ''
  } catch (e) {
    if (token !== clusterToken) return
    cluster.value = null
    clusterScore.value = null
    clusterError.value = e.message || '连号簇加载失败'
  } finally {
    if (token === clusterToken) clusterBoardLoading.value = false
  }
}

async function runCluster() {
  clusterLoading.value = true
  clusterError.value = ''
  const params = clusterWindows()
  try {
    const main = splitNums(clusterMain.value)
    const special = echoField.value.specialLabel ? splitNums(clusterSpecial.value) : []
    const body = await postCluster(type.value, { main, special, ...params })
    cluster.value = body
    clusterScore.value = body
  } catch (e) {
    clusterScore.value = null
    clusterError.value = e.message || '打分失败'
  } finally {
    clusterLoading.value = false
  }
}

function roadWindows() {
  let limit = Math.round(Number(roadLimit.value))
  let short = Math.round(Number(roadShort.value))
  let long = Math.round(Number(roadLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  roadLimit.value = limit
  roadShort.value = short
  roadLong.value = long
  return { limit, short, long }
}

function roadDriftLabel(drift) {
  if (drift === 'rising') return '更偏'
  if (drift === 'falling') return '更匀'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function roadCountText(counts) {
  if (!counts) return ''
  return `0路 ${counts['0'] ?? 0} · 1路 ${counts['1'] ?? 0} · 2路 ${counts['2'] ?? 0}`
}

function roadCurrent(value) {
  return roadScore.value?.ticket?.imbalance === value
}

async function loadRoad() {
  const token = ++roadToken
  roadBoardLoading.value = true
  const params = roadWindows()
  try {
    const body = await getRoad(type.value, params)
    if (token !== roadToken) return
    road.value = body
    roadScore.value = null
    roadError.value = ''
  } catch (e) {
    if (token !== roadToken) return
    road.value = null
    roadScore.value = null
    roadError.value = e.message || '012路加载失败'
  } finally {
    if (token === roadToken) roadBoardLoading.value = false
  }
}

async function runRoad() {
  roadLoading.value = true
  roadError.value = ''
  const params = roadWindows()
  try {
    const main = splitNums(roadMain.value)
    const special = echoField.value.specialLabel ? splitNums(roadSpecial.value) : []
    const body = await postRoad(type.value, { main, special, ...params })
    road.value = body
    roadScore.value = body
  } catch (e) {
    roadScore.value = null
    roadError.value = e.message || '打分失败'
  } finally {
    roadLoading.value = false
  }
}

function sumWindows() {
  let limit = Math.round(Number(sumLimit.value))
  let short = Math.round(Number(sumShort.value))
  let long = Math.round(Number(sumLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  sumLimit.value = limit
  sumShort.value = short
  sumLong.value = long
  return { limit, short, long }
}

function sumDriftLabel(drift) {
  if (drift === 'rising') return '走高'
  if (drift === 'falling') return '走低'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function sumCurrent(value) {
  return sumScore.value?.ticket?.sum === value
}

async function loadSum() {
  const token = ++sumToken
  sumBoardLoading.value = true
  const params = sumWindows()
  try {
    const body = await getSum(type.value, params)
    if (token !== sumToken) return
    sumPulse.value = body
    sumScore.value = null
    sumError.value = ''
  } catch (e) {
    if (token !== sumToken) return
    sumPulse.value = null
    sumScore.value = null
    sumError.value = e.message || '和值加载失败'
  } finally {
    if (token === sumToken) sumBoardLoading.value = false
  }
}

async function runSum() {
  sumLoading.value = true
  sumError.value = ''
  const params = sumWindows()
  try {
    const main = splitNums(sumMain.value)
    const special = echoField.value.specialLabel ? splitNums(sumSpecial.value) : []
    const body = await postSum(type.value, { main, special, ...params })
    sumPulse.value = body
    sumScore.value = body
  } catch (e) {
    sumScore.value = null
    sumError.value = e.message || '打分失败'
  } finally {
    sumLoading.value = false
  }
}

async function fillLatestSum() {
  sumError.value = ''
  if (!sumPulse.value) await loadSum()
  const latest = sumPulse.value?.latest_draw
  if (!latest) {
    sumScore.value = null
    sumError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  sumMain.value = (latest.main || []).join(' ')
  sumSpecial.value = (latest.special || []).join(' ')
  await runSum()
}

function parityWindows() {
  let limit = Math.round(Number(parityLimit.value))
  let short = Math.round(Number(parityShort.value))
  let long = Math.round(Number(parityLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  parityLimit.value = limit
  parityShort.value = short
  parityLong.value = long
  return { limit, short, long }
}

function parityDriftLabel(drift) {
  if (drift === 'rising') return '走高'
  if (drift === 'falling') return '走低'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function parityCurrent(value) {
  return parityScore.value?.ticket?.odd_count === value
}

async function loadParity() {
  const token = ++parityToken
  parityBoardLoading.value = true
  const params = parityWindows()
  try {
    const body = await getParity(type.value, params)
    if (token !== parityToken) return
    parity.value = body
    parityScore.value = null
    parityError.value = ''
  } catch (e) {
    if (token !== parityToken) return
    parity.value = null
    parityScore.value = null
    parityError.value = e.message || '奇偶加载失败'
  } finally {
    if (token === parityToken) parityBoardLoading.value = false
  }
}

async function runParity() {
  parityLoading.value = true
  parityError.value = ''
  const params = parityWindows()
  try {
    const main = splitNums(parityMain.value)
    const special = echoField.value.specialLabel ? splitNums(paritySpecial.value) : []
    const body = await postParity(type.value, { main, special, ...params })
    parity.value = body
    parityScore.value = body
  } catch (e) {
    parityScore.value = null
    parityError.value = e.message || '打分失败'
  } finally {
    parityLoading.value = false
  }
}

async function fillLatestParity() {
  parityError.value = ''
  if (!parity.value) await loadParity()
  const latest = parity.value?.latest_draw
  if (!latest) {
    parityScore.value = null
    parityError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  parityMain.value = (latest.main || []).join(' ')
  paritySpecial.value = (latest.special || []).join(' ')
  await runParity()
}

function primeWindows() {
  let limit = Math.round(Number(primeLimit.value))
  let short = Math.round(Number(primeShort.value))
  let long = Math.round(Number(primeLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  primeLimit.value = limit
  primeShort.value = short
  primeLong.value = long
  return { limit, short, long }
}

function primeCurrent(value) {
  return primeScore.value?.ticket?.prime_count === value
}

async function loadPrime() {
  const token = ++primeToken
  primeBoardLoading.value = true
  const params = primeWindows()
  try {
    const body = await getPrime(type.value, params)
    if (token !== primeToken) return
    prime.value = body
    primeScore.value = null
    primeError.value = ''
  } catch (e) {
    if (token !== primeToken) return
    prime.value = null
    primeScore.value = null
    primeError.value = e.message || '质合加载失败'
  } finally {
    if (token === primeToken) primeBoardLoading.value = false
  }
}

async function runPrime() {
  primeLoading.value = true
  primeError.value = ''
  const params = primeWindows()
  try {
    const main = splitNums(primeMain.value)
    const special = echoField.value.specialLabel ? splitNums(primeSpecial.value) : []
    const body = await postPrime(type.value, { main, special, ...params })
    prime.value = body
    primeScore.value = body
  } catch (e) {
    primeScore.value = null
    primeError.value = e.message || '打分失败'
  } finally {
    primeLoading.value = false
  }
}

function zoneWindows() {
  let limit = Math.round(Number(zoneLimit.value))
  let short = Math.round(Number(zoneShort.value))
  let long = Math.round(Number(zoneLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  zoneLimit.value = limit
  zoneShort.value = short
  zoneLong.value = long
  return { limit, short, long }
}

function zoneDriftLabel(drift) {
  if (drift === 'rising') return '更偏'
  if (drift === 'falling') return '更匀'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function zoneRangeText(item, zones) {
  if (!item) return ''
  const pad = (zones || [item]).some((zone) => zone.lo > 9 || zone.hi > 9)
  const text = (value) => (pad ? String(value).padStart(2, '0') : String(value))
  return `${item.name} ${text(item.lo)}–${text(item.hi)}`
}

function zoneCurrent(value) {
  return zoneScore.value?.ticket?.imbalance === value
}

async function loadZone() {
  const token = ++zoneToken
  zoneBoardLoading.value = true
  const params = zoneWindows()
  try {
    const body = await getZone(type.value, params)
    if (token !== zoneToken) return
    zone.value = body
    zoneScore.value = null
    zoneError.value = ''
  } catch (e) {
    if (token !== zoneToken) return
    zone.value = null
    zoneScore.value = null
    zoneError.value = e.message || '区位加载失败'
  } finally {
    if (token === zoneToken) zoneBoardLoading.value = false
  }
}

async function runZone() {
  zoneLoading.value = true
  zoneError.value = ''
  const params = zoneWindows()
  try {
    const main = splitNums(zoneMain.value)
    const special = echoField.value.specialLabel ? splitNums(zoneSpecial.value) : []
    const body = await postZone(type.value, { main, special, ...params })
    zone.value = body
    zoneScore.value = body
  } catch (e) {
    zoneScore.value = null
    zoneError.value = e.message || '打分失败'
  } finally {
    zoneLoading.value = false
  }
}

function tailWindows() {
  let limit = Math.round(Number(tailLimit.value))
  let short = Math.round(Number(tailShort.value))
  let long = Math.round(Number(tailLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  tailLimit.value = limit
  tailShort.value = short
  tailLong.value = long
  return { limit, short, long }
}

function tailDriftLabel(drift) {
  if (drift === 'rising') return '更散'
  if (drift === 'falling') return '更集中'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function tailSpeak(tails) {
  return (tails || []).join('、') || '—'
}

function tailCurrent(value) {
  return tailScore.value?.ticket?.unique_tail_count === value
}

async function loadTail() {
  const token = ++tailToken
  tailBoardLoading.value = true
  const params = tailWindows()
  try {
    const body = await getTail(type.value, params)
    if (token !== tailToken) return
    tail.value = body
    tailScore.value = null
    tailError.value = ''
  } catch (e) {
    if (token !== tailToken) return
    tail.value = null
    tailScore.value = null
    tailError.value = e.message || '尾数加载失败'
  } finally {
    if (token === tailToken) tailBoardLoading.value = false
  }
}

async function runTail() {
  tailLoading.value = true
  tailError.value = ''
  const params = tailWindows()
  try {
    const main = splitNums(tailMain.value)
    const special = echoField.value.specialLabel ? splitNums(tailSpecial.value) : []
    const body = await postTail(type.value, { main, special, ...params })
    tail.value = body
    tailScore.value = body
  } catch (e) {
    tailScore.value = null
    tailError.value = e.message || '打分失败'
  } finally {
    tailLoading.value = false
  }
}

async function fillLatestTail() {
  tailError.value = ''
  if (!tail.value) await loadTail()
  const latest = tail.value?.latest_draw
  if (!latest) {
    tailScore.value = null
    tailError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  tailMain.value = (latest.main || []).join(' ')
  tailSpecial.value = (latest.special || []).join(' ')
  await runTail()
}

function acWindows() {
  let limit = Math.round(Number(acLimit.value))
  let short = Math.round(Number(acShort.value))
  let long = Math.round(Number(acLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  acLimit.value = limit
  acShort.value = short
  acLong.value = long
  return { limit, short, long }
}

function acDriftLabel(drift) {
  if (drift === 'rising') return '走高'
  if (drift === 'falling') return '走低'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function acCurrent(value) {
  return acScore.value?.ticket?.ac_value === value
}

async function loadAc() {
  const token = ++acToken
  acBoardLoading.value = true
  const params = acWindows()
  try {
    const body = await getAc(type.value, params)
    if (token !== acToken) return
    acPulse.value = body
    acScore.value = null
    acError.value = ''
  } catch (e) {
    if (token !== acToken) return
    acPulse.value = null
    acScore.value = null
    acError.value = e.message || 'AC值加载失败'
  } finally {
    if (token === acToken) acBoardLoading.value = false
  }
}

async function runAc() {
  acLoading.value = true
  acError.value = ''
  const params = acWindows()
  try {
    const main = splitNums(acMain.value)
    const special = echoField.value.specialLabel ? splitNums(acSpecial.value) : []
    const body = await postAc(type.value, { main, special, ...params })
    acPulse.value = body
    acScore.value = body
  } catch (e) {
    acScore.value = null
    acError.value = e.message || '打分失败'
  } finally {
    acLoading.value = false
  }
}

async function fillLatestAc() {
  acError.value = ''
  if (!acPulse.value) await loadAc()
  const latest = acPulse.value?.latest_draw
  if (!latest) {
    acScore.value = null
    acError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  acMain.value = (latest.main || []).join(' ')
  acSpecial.value = (latest.special || []).join(' ')
  await runAc()
}

function heweiWindows() {
  let limit = Math.round(Number(heweiLimit.value))
  let short = Math.round(Number(heweiShort.value))
  let long = Math.round(Number(heweiLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  heweiLimit.value = limit
  heweiShort.value = short
  heweiLong.value = long
  return { limit, short, long }
}

function heweiDriftLabel(drift) {
  if (drift === 'rising') return '走高'
  if (drift === 'falling') return '走低'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function heweiCurrent(value) {
  return heweiScore.value?.ticket?.hewei === value
}

async function loadHewei() {
  const token = ++heweiToken
  heweiBoardLoading.value = true
  const params = heweiWindows()
  try {
    const body = await getHewei(type.value, params)
    if (token !== heweiToken) return
    heweiPulse.value = body
    heweiScore.value = null
    heweiError.value = ''
  } catch (e) {
    if (token !== heweiToken) return
    heweiPulse.value = null
    heweiScore.value = null
    heweiError.value = e.message || '和尾加载失败'
  } finally {
    if (token === heweiToken) heweiBoardLoading.value = false
  }
}

async function runHewei() {
  heweiLoading.value = true
  heweiError.value = ''
  const params = heweiWindows()
  try {
    const main = splitNums(heweiMain.value)
    const special = echoField.value.specialLabel ? splitNums(heweiSpecial.value) : []
    const body = await postHewei(type.value, { main, special, ...params })
    heweiPulse.value = body
    heweiScore.value = body
  } catch (e) {
    heweiScore.value = null
    heweiError.value = e.message || '打分失败'
  } finally {
    heweiLoading.value = false
  }
}

async function fillLatestHewei() {
  heweiError.value = ''
  if (!heweiPulse.value) await loadHewei()
  const latest = heweiPulse.value?.latest_draw
  if (!latest) {
    heweiScore.value = null
    heweiError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  heweiMain.value = (latest.main || []).join(' ')
  heweiSpecial.value = (latest.special || []).join(' ')
  await runHewei()
}

function daxiaoWindows() {
  let limit = Math.round(Number(daxiaoLimit.value))
  let short = Math.round(Number(daxiaoShort.value))
  let long = Math.round(Number(daxiaoLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  daxiaoLimit.value = limit
  daxiaoShort.value = short
  daxiaoLong.value = long
  return { limit, short, long }
}

function daxiaoDriftLabel(drift) {
  if (drift === 'rising') return '走高'
  if (drift === 'falling') return '走低'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function daxiaoCutoff(boundary) {
  if (!boundary) return ''
  return `${boundary.lo}–${boundary.mid} 小，${boundary.mid + 1}–${boundary.hi} 大`
}

function daxiaoRatio(big, small) {
  if (big == null || small == null) return ''
  return `${big}大${small}小`
}

function daxiaoCurrent(value) {
  return daxiaoScore.value?.ticket?.big_count === value
}

async function loadDaxiao() {
  const token = ++daxiaoToken
  daxiaoBoardLoading.value = true
  const params = daxiaoWindows()
  try {
    const body = await getDaxiao(type.value, params)
    if (token !== daxiaoToken) return
    daxiao.value = body
    daxiaoScore.value = null
    daxiaoError.value = ''
  } catch (e) {
    if (token !== daxiaoToken) return
    daxiao.value = null
    daxiaoScore.value = null
    daxiaoError.value = e.message || '大小加载失败'
  } finally {
    if (token === daxiaoToken) daxiaoBoardLoading.value = false
  }
}

async function runDaxiao() {
  daxiaoLoading.value = true
  daxiaoError.value = ''
  const params = daxiaoWindows()
  try {
    const main = splitNums(daxiaoMain.value)
    const special = echoField.value.specialLabel ? splitNums(daxiaoSpecial.value) : []
    const body = await postDaxiao(type.value, { main, special, ...params })
    daxiao.value = body
    daxiaoScore.value = body
  } catch (e) {
    daxiaoScore.value = null
    daxiaoError.value = e.message || '打分失败'
  } finally {
    daxiaoLoading.value = false
  }
}

async function fillLatestDaxiao() {
  daxiaoError.value = ''
  if (!daxiao.value) await loadDaxiao()
  const latest = daxiao.value?.latest_draw
  if (!latest) {
    daxiaoScore.value = null
    daxiaoError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  daxiaoMain.value = (latest.main || []).join(' ')
  daxiaoSpecial.value = (latest.special || []).join(' ')
  await runDaxiao()
}

function shengpingWindows() {
  let limit = Math.round(Number(shengpingLimit.value))
  let short = Math.round(Number(shengpingShort.value))
  let long = Math.round(Number(shengpingLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  shengpingLimit.value = limit
  shengpingShort.value = short
  shengpingLong.value = long
  return { limit, short, long }
}

function shengpingDriftLabel(drift) {
  if (drift === 'rising') return '走高'
  if (drift === 'falling') return '走低'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function shengpingCurrent(value) {
  return shengpingScore.value?.ticket?.rise_count === value
}

async function loadShengping() {
  const token = ++shengpingToken
  shengpingBoardLoading.value = true
  const params = shengpingWindows()
  try {
    const body = await getShengping(type.value, params)
    if (token !== shengpingToken) return
    shengping.value = body
    shengpingScore.value = null
    shengpingError.value = ''
  } catch (e) {
    if (token !== shengpingToken) return
    shengping.value = null
    shengpingScore.value = null
    shengpingError.value = e.message || '升平降加载失败'
  } finally {
    if (token === shengpingToken) shengpingBoardLoading.value = false
  }
}

async function runShengping() {
  shengpingLoading.value = true
  shengpingError.value = ''
  const params = shengpingWindows()
  try {
    const main = splitNums(shengpingMain.value)
    const special = echoField.value.specialLabel ? splitNums(shengpingSpecial.value) : []
    const body = await postShengping(type.value, { main, special, ...params })
    shengping.value = body
    shengpingScore.value = body
  } catch (e) {
    shengpingScore.value = null
    shengpingError.value = e.message || '打分失败'
  } finally {
    shengpingLoading.value = false
  }
}

async function fillLatestShengping() {
  shengpingError.value = ''
  if (!shengping.value) await loadShengping()
  const latest = shengping.value?.latest_draw
  if (!latest) {
    shengpingScore.value = null
    shengpingError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  shengpingMain.value = (latest.main || []).join(' ')
  shengpingSpecial.value = (latest.special || []).join(' ')
  await runShengping()
}

function zhenfuWindows() {
  let limit = Math.round(Number(zhenfuLimit.value))
  let short = Math.round(Number(zhenfuShort.value))
  let long = Math.round(Number(zhenfuLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  zhenfuLimit.value = limit
  zhenfuShort.value = short
  zhenfuLong.value = long
  return { limit, short, long }
}

function zhenfuDriftLabel(drift) {
  if (drift === 'rising') return '走高'
  if (drift === 'falling') return '走低'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function zhenfuCurrent(value) {
  return zhenfuScore.value?.ticket?.amplitude_sum === value
}

async function loadZhenfu() {
  const token = ++zhenfuToken
  zhenfuBoardLoading.value = true
  const params = zhenfuWindows()
  try {
    const body = await getZhenfu(type.value, params)
    if (token !== zhenfuToken) return
    zhenfu.value = body
    zhenfuScore.value = null
    zhenfuError.value = ''
  } catch (e) {
    if (token !== zhenfuToken) return
    zhenfu.value = null
    zhenfuScore.value = null
    zhenfuError.value = e.message || '振幅加载失败'
  } finally {
    if (token === zhenfuToken) zhenfuBoardLoading.value = false
  }
}

async function runZhenfu() {
  zhenfuLoading.value = true
  zhenfuError.value = ''
  const params = zhenfuWindows()
  try {
    const main = splitNums(zhenfuMain.value)
    const special = echoField.value.specialLabel ? splitNums(zhenfuSpecial.value) : []
    const body = await postZhenfu(type.value, { main, special, ...params })
    zhenfu.value = body
    zhenfuScore.value = body
  } catch (e) {
    zhenfuScore.value = null
    zhenfuError.value = e.message || '打分失败'
  } finally {
    zhenfuLoading.value = false
  }
}

async function fillLatestZhenfu() {
  zhenfuError.value = ''
  if (!zhenfu.value) await loadZhenfu()
  const latest = zhenfu.value?.latest_draw
  if (!latest) {
    zhenfuScore.value = null
    zhenfuError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  zhenfuMain.value = (latest.main || []).join(' ')
  zhenfuSpecial.value = (latest.special || []).join(' ')
  await runZhenfu()
}

function junzhiWindows() {
  let limit = Math.round(Number(junzhiLimit.value))
  let short = Math.round(Number(junzhiShort.value))
  let long = Math.round(Number(junzhiLong.value))
  if (!Number.isFinite(limit)) limit = 80
  if (!Number.isFinite(short)) short = 10
  if (!Number.isFinite(long)) long = 50
  limit = Math.min(200, Math.max(5, limit))
  short = Math.min(30, Math.max(5, short))
  long = Math.min(200, Math.max(20, long))
  if (long <= short) long = Math.min(200, short + 1)
  junzhiLimit.value = limit
  junzhiShort.value = short
  junzhiLong.value = long
  return { limit, short, long }
}

function junzhiDriftLabel(drift) {
  if (drift === 'rising') return '走高'
  if (drift === 'falling') return '走低'
  if (drift === 'flat') return '持平'
  return '暂无'
}

function junzhiCurrent(value) {
  return Number(junzhiScore.value?.ticket?.mean_value) === Number(value)
}

async function loadJunzhi() {
  const token = ++junzhiToken
  junzhiBoardLoading.value = true
  const params = junzhiWindows()
  try {
    const body = await getJunzhi(type.value, params)
    if (token !== junzhiToken) return
    junzhi.value = body
    junzhiScore.value = null
    junzhiError.value = ''
  } catch (e) {
    if (token !== junzhiToken) return
    junzhi.value = null
    junzhiScore.value = null
    junzhiError.value = e.message || '均值加载失败'
  } finally {
    if (token === junzhiToken) junzhiBoardLoading.value = false
  }
}

async function runJunzhi() {
  junzhiLoading.value = true
  junzhiError.value = ''
  const params = junzhiWindows()
  try {
    const main = splitNums(junzhiMain.value)
    const special = echoField.value.specialLabel ? splitNums(junzhiSpecial.value) : []
    const body = await postJunzhi(type.value, { main, special, ...params })
    junzhi.value = body
    junzhiScore.value = body
  } catch (e) {
    junzhiScore.value = null
    junzhiError.value = e.message || '打分失败'
  } finally {
    junzhiLoading.value = false
  }
}

async function fillLatestJunzhi() {
  junzhiError.value = ''
  if (!junzhi.value) await loadJunzhi()
  const latest = junzhi.value?.latest_draw
  if (!latest) {
    junzhiScore.value = null
    junzhiError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  junzhiMain.value = (latest.main || []).join(' ')
  junzhiSpecial.value = (latest.special || []).join(' ')
  await runJunzhi()
}

async function fillLatestZone() {
  zoneError.value = ''
  if (!zone.value) await loadZone()
  const latest = zone.value?.latest_draw
  if (!latest) {
    zoneScore.value = null
    zoneError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  zoneMain.value = (latest.main || []).join(' ')
  zoneSpecial.value = (latest.special || []).join(' ')
  await runZone()
}

async function fillLatestPrime() {
  primeError.value = ''
  if (!prime.value) await loadPrime()
  const latest = prime.value?.latest_draw
  if (!latest) {
    primeScore.value = null
    primeError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  primeMain.value = (latest.main || []).join(' ')
  primeSpecial.value = (latest.special || []).join(' ')
  await runPrime()
}

async function fillLatestRoad() {
  roadError.value = ''
  if (!road.value) await loadRoad()
  const latest = road.value?.latest_draw
  if (!latest) {
    roadScore.value = null
    roadError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  roadMain.value = (latest.main || []).join(' ')
  roadSpecial.value = (latest.special || []).join(' ')
  await runRoad()
}

async function fillLatestCluster() {
  clusterError.value = ''
  if (!cluster.value) await loadCluster()
  const latest = cluster.value?.latest_draw
  if (!latest) {
    clusterScore.value = null
    clusterError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  clusterMain.value = (latest.main || []).join(' ')
  clusterSpecial.value = (latest.special || []).join(' ')
  await runCluster()
}

async function fillLatestSpan() {
  spanError.value = ''
  if (!span.value) await loadSpan()
  const latest = span.value?.latest_draw
  if (!latest) {
    spanScore.value = null
    spanError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  spanMain.value = (latest.main || []).join(' ')
  spanSpecial.value = (latest.special || []).join(' ')
  await runSpan()
}

async function fillLatestNeighbor() {
  neighborError.value = ''
  if (!neighbor.value) await loadNeighbor()
  const latest = neighbor.value?.latest_draw
  if (!latest) {
    neighborScore.value = null
    neighborError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  neighborMain.value = (latest.main || []).join(' ')
  neighborSpecial.value = (latest.special || []).join(' ')
  await runNeighbor()
}

async function fillLatestMomentum() {
  momentumError.value = ''
  if (!momentum.value) await loadMomentum()
  const latest = momentum.value?.latest_draw
  if (!latest) {
    momentumScore.value = null
    momentumError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  momentumMain.value = (latest.main || []).join(' ')
  momentumSpecial.value = (latest.special || []).join(' ')
  await runMomentum()
}

async function fillLatestRepeat() {
  repeatError.value = ''
  if (!repeatPulse.value) await loadRepeat()
  const latest = repeatPulse.value?.latest_draw
  if (!latest) {
    repeatScore.value = null
    repeatError.value = '暂无开奖可对照。仅供娱乐，不构成投注建议。'
    return
  }
  repeatMain.value = (latest.main || []).join(' ')
  repeatSpecial.value = (latest.special || []).join(' ')
  await runRepeat()
}

async function runCollision(fromRecords) {
  collisionLoading.value = true
  collisionError.value = ''
  try {
    const body = fromRecords
      ? { from_records: true, tickets: [] }
      : { from_records: false, tickets: collisionTickets.value.map(collisionPayload) }
    collisionResult.value = await api.collision(type.value, body)
  } catch (e) {
    collisionResult.value = null
    collisionError.value = e.message || '撞车对照失败'
  } finally {
    collisionLoading.value = false
  }
}

async function applyCollisionPaste() {
  const lines = collisionPaste.value.split(/\n/).map((line) => line.trim()).filter(Boolean)
  if (lines.length < 2) {
    collisionError.value = '一行一注，至少贴两行'
    collisionResult.value = null
    return
  }
  collisionTickets.value = lines.slice(0, 20).map((line) => {
    const ticket = blankCollisionTicket()
    const parts = line.split(/\s*[+|｜]\s*/)
    ticket.mainText = (parts[0] || '').trim()
    ticket.specialText = (parts[1] || '').trim()
    fillCollisionDigits(ticket)
    return ticket
  })
  await runCollision(false)
}

function resetCollision() {
  collisionResult.value = null
  collisionError.value = ''
  collisionPaste.value = ''
  collisionUsePad.value = false
  collisionTickets.value = [blankCollisionTicket(), blankCollisionTicket()]
}

function load() {
  shape.value = null
  echoResult.value = null
  echoError.value = ''
  echoMain.value = ''
  echoSpecial.value = ''
  affinity.value = null
  affinityError.value = ''
  affinitySeed.value = ''
  resetCollision()
  repeatPulse.value = null
  repeatScore.value = null
  repeatError.value = ''
  repeatMain.value = ''
  repeatSpecial.value = ''
  momentum.value = null
  momentumScore.value = null
  momentumError.value = ''
  momentumMain.value = ''
  momentumSpecial.value = ''
  momentumShort.value = 10
  momentumLong.value = 50
  neighbor.value = null
  neighborScore.value = null
  neighborError.value = ''
  neighborMain.value = ''
  neighborSpecial.value = ''
  neighborLimit.value = 80
  neighborHorizon.value = 3
  span.value = null
  spanScore.value = null
  spanError.value = ''
  spanMain.value = ''
  spanSpecial.value = ''
  spanLimit.value = 80
  spanShort.value = 10
  spanLong.value = 50
  cluster.value = null
  clusterScore.value = null
  clusterError.value = ''
  clusterMain.value = ''
  clusterSpecial.value = ''
  clusterLimit.value = 80
  clusterShort.value = 10
  clusterLong.value = 50
  road.value = null
  roadScore.value = null
  roadError.value = ''
  roadMain.value = ''
  roadSpecial.value = ''
  roadLimit.value = 80
  roadShort.value = 10
  roadLong.value = 50
  sumPulse.value = null
  sumScore.value = null
  sumError.value = ''
  sumMain.value = ''
  sumSpecial.value = ''
  sumLimit.value = 80
  sumShort.value = 10
  sumLong.value = 50
  parity.value = null
  parityScore.value = null
  parityError.value = ''
  parityMain.value = ''
  paritySpecial.value = ''
  parityLimit.value = 80
  parityShort.value = 10
  parityLong.value = 50
  prime.value = null
  primeScore.value = null
  primeError.value = ''
  primeMain.value = ''
  primeSpecial.value = ''
  primeLimit.value = 80
  primeShort.value = 10
  primeLong.value = 50
  zone.value = null
  zoneScore.value = null
  zoneError.value = ''
  zoneMain.value = ''
  zoneSpecial.value = ''
  zoneLimit.value = 80
  zoneShort.value = 10
  zoneLong.value = 50
  tail.value = null
  tailScore.value = null
  tailError.value = ''
  tailMain.value = ''
  tailSpecial.value = ''
  tailLimit.value = 80
  tailShort.value = 10
  tailLong.value = 50
  acPulse.value = null
  acScore.value = null
  acError.value = ''
  acMain.value = ''
  acSpecial.value = ''
  acLimit.value = 80
  acShort.value = 10
  acLong.value = 50
  heweiPulse.value = null
  heweiScore.value = null
  heweiError.value = ''
  heweiMain.value = ''
  heweiSpecial.value = ''
  heweiLimit.value = 80
  heweiShort.value = 10
  heweiLong.value = 50
  daxiao.value = null
  daxiaoScore.value = null
  daxiaoError.value = ''
  daxiaoMain.value = ''
  daxiaoSpecial.value = ''
  daxiaoLimit.value = 80
  daxiaoShort.value = 10
  daxiaoLong.value = 50
  shengping.value = null
  shengpingScore.value = null
  shengpingError.value = ''
  shengpingMain.value = ''
  shengpingSpecial.value = ''
  shengpingLimit.value = 80
  shengpingShort.value = 10
  shengpingLong.value = 50
  zhenfu.value = null
  zhenfuScore.value = null
  zhenfuError.value = ''
  zhenfuMain.value = ''
  zhenfuSpecial.value = ''
  zhenfuLimit.value = 80
  zhenfuShort.value = 10
  zhenfuLong.value = 50
  junzhi.value = null
  junzhiScore.value = null
  junzhiError.value = ''
  junzhiMain.value = ''
  junzhiSpecial.value = ''
  junzhiLimit.value = 80
  junzhiShort.value = 10
  junzhiLong.value = 50
  loadDraws()
  loadAnalysis()
  loadAffinity()
  loadRepeat()
  loadMomentum()
  loadNeighbor()
  loadSpan()
  loadCluster()
  loadRoad()
  loadSum()
  loadParity()
  loadPrime()
  loadZone()
  loadTail()
  loadAc()
  loadHewei()
  loadDaxiao()
  loadShengping()
  loadZhenfu()
  loadJunzhi()
}

watch(periods, () => {
  loadAnalysis()
  loadAffinity()
})

watch(() => route.query.type, (next) => {
  if (next && next !== type.value && TYPE_NAMES[next]) {
    type.value = next
    load()
  }
})

onMounted(load)
</script>
