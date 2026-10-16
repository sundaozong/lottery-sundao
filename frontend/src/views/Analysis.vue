<template>
  <div>
    <div class="page-header">
      <div>
        <h1>分析中心</h1>
        <p>开奖走势 · 冷热频次 · 遗漏 · 热力 · 回声 · 结伴 · 撞车 · 脉搏</p>
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
import { api, TYPE_NAMES, ballClass } from '../api'
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
  loadDraws()
  loadAnalysis()
  loadAffinity()
  loadRepeat()
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
